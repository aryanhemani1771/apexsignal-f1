"""FastF1 historical adapter — real F1 timing/telemetry → domain events.

FastF1 (MIT) is the authoritative historical data source (see ``REFERENCES.md``). It needs
**no credentials**, only network access for the first download of a session; results are
cached on disk thereafter. ``fastf1`` lives in the optional ``data`` dependency group and is
imported lazily so this module stays importable in the credential-free / CI environment.

Time handling: FastF1 exposes lap/weather/track ``Time`` values as session-relative
``Timedelta`` s measured from an anchor ``t0`` (where session time == 0), while race-control
messages carry absolute timestamps. We recover ``t0`` from the scheduled session date minus
FastF1's ``session_start_time`` offset, then convert relative times onto the same absolute
UTC timeline so every event stream aligns. For a completed historical race each observation
is treated as first seen when it occurred (``first_seen_at == event_time``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apexsignal.domain.events import DomainEvent, EventType, sort_key
from apexsignal.logging import get_logger

log = get_logger("fastf1_adapter")


class FastF1NotInstalledError(RuntimeError):
    """Raised when the optional ``data`` extra (fastf1) is not installed."""


def _require_fastf1() -> Any:
    try:
        import fastf1
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise FastF1NotInstalledError(
            "fastf1 is not installed. Install the data extra: `uv sync --extra data`."
        ) from exc
    return fastf1


def _to_utc(value: Any) -> datetime | None:
    """Coerce an absolute pandas/py datetime to a tz-aware UTC datetime, or None."""
    if value is None:
        return None
    try:
        import pandas as pd

        if pd.isna(value):
            return None
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None
    dt: datetime = ts.to_pydatetime()
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _seconds(value: Any) -> float | None:
    """Total seconds of a Timedelta-like value, or None."""
    try:
        import pandas as pd

        if value is None or pd.isna(value):
            return None
        return float(pd.Timedelta(value).total_seconds())
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def _rel_to_abs(t0: datetime | None, value: Any) -> datetime | None:
    """Convert a session-relative Timedelta to an absolute UTC datetime given ``t0``."""
    secs = _seconds(value)
    if t0 is None or secs is None:
        return None
    return t0 + timedelta(seconds=secs)


class FastF1Adapter:
    """Loads a completed FastF1 session and emits :class:`DomainEvent` objects."""

    def __init__(self, cache_dir: str | Path = ".cache/fastf1") -> None:
        self._cache_dir = Path(cache_dir)
        self._fastf1 = _require_fastf1()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._fastf1.Cache.enable_cache(str(self._cache_dir))

    def load_session_events(
        self, season: int, event: int | str, session: str = "R"
    ) -> list[DomainEvent]:
        """Download (or read from cache) a session and return time-ordered domain events."""
        ff1_session = self._fastf1.get_session(season, event, session)
        ff1_session.load(laps=True, telemetry=False, weather=True, messages=True)

        meeting_id = f"{season}-{getattr(ff1_session.event, 'RoundNumber', event)}"
        session_id = f"{meeting_id}-{session}"
        now = datetime.now(UTC)
        t0 = self._session_t0(ff1_session)

        events: list[DomainEvent] = []
        events += self._lap_events(ff1_session, meeting_id, session_id, now, t0)
        events += self._weather_events(ff1_session, meeting_id, session_id, now, t0)
        events += self._track_status_events(ff1_session, meeting_id, session_id, now, t0)
        events += self._race_control_events(ff1_session, meeting_id, session_id, now)
        # Each pass emits chronologically; interleave into one clean time-ordered stream.
        events.sort(key=sort_key)
        log.info(
            "fastf1.loaded",
            season=season,
            event_ref=str(event),
            session=session,
            has_t0=t0 is not None,
            n_events=len(events),
        )
        return events

    @staticmethod
    def _session_t0(s: Any) -> datetime | None:
        """Absolute UTC datetime where session ``Time == 0`` (anchor for relative times)."""
        try:
            import pandas as pd

            date = pd.Timestamp(s.date)
            offset = pd.Timedelta(s.session_start_time)
        except (TypeError, ValueError, AttributeError):  # pragma: no cover - defensive
            return None
        if pd.isna(date) or pd.isna(offset):
            return None
        t0: datetime = (date - offset).to_pydatetime()
        return t0.replace(tzinfo=UTC) if t0.tzinfo is None else t0.astimezone(UTC)

    def _lap_events(
        self, s: Any, meeting_id: str, session_id: str, ingested: datetime, t0: datetime | None
    ) -> list[DomainEvent]:
        laps = getattr(s, "laps", None)
        if laps is None or len(laps) == 0:
            return []
        out: list[DomainEvent] = []
        for _, lap in laps.iterrows():
            end_time = _rel_to_abs(t0, lap.get("Time"))
            if end_time is None:
                continue
            driver = str(lap.get("Driver") or lap.get("DriverNumber") or "UNK")
            team = _slug(lap.get("Team"))
            payload: dict[str, Any] = {
                "lap": _int_or_none(lap.get("LapNumber")),
                "position": _int_or_none(lap.get("Position")),
                "lap_time": _seconds(lap.get("LapTime")),
                "tyre": _str_or_none(lap.get("Compound")),
                "tyre_age": _int_or_none(lap.get("TyreLife")),
                "stint": _int_or_none(lap.get("Stint")),
            }
            out.append(
                DomainEvent(
                    event_type=EventType.LAP_COMPLETED,
                    source="fastf1",
                    event_time=end_time,
                    first_seen_at=end_time,
                    ingested_at=ingested,
                    meeting_id=meeting_id,
                    session_id=session_id,
                    driver_id=driver,
                    constructor_id=team,
                    payload={k: v for k, v in payload.items() if v is not None},
                )
            )
            if _seconds(lap.get("PitInTime")) is not None:
                out.append(
                    DomainEvent(
                        event_type=EventType.PIT_STOP_COMPLETED,
                        source="fastf1",
                        event_time=end_time,
                        first_seen_at=end_time,
                        ingested_at=ingested,
                        meeting_id=meeting_id,
                        session_id=session_id,
                        driver_id=driver,
                        constructor_id=team,
                        payload={"lap": _int_or_none(lap.get("LapNumber"))},
                    )
                )
        return out

    def _weather_events(
        self, s: Any, meeting_id: str, session_id: str, ingested: datetime, t0: datetime | None
    ) -> list[DomainEvent]:
        weather = getattr(s, "weather_data", None)
        if weather is None or len(weather) == 0:
            return []
        out: list[DomainEvent] = []
        for _, row in weather.iterrows():
            t = _rel_to_abs(t0, row.get("Time")) or ingested
            rain = row.get("Rainfall")
            out.append(
                DomainEvent(
                    event_type=EventType.WEATHER_UPDATED,
                    source="fastf1",
                    event_time=t,
                    first_seen_at=t,
                    ingested_at=ingested,
                    meeting_id=meeting_id,
                    session_id=session_id,
                    payload={
                        "air_temp": _float_or_none(row.get("AirTemp")),
                        "track_temp": _float_or_none(row.get("TrackTemp")),
                        "rainfall": bool(rain) if rain is not None else None,
                        "humidity": _float_or_none(row.get("Humidity")),
                    },
                )
            )
        return out

    def _track_status_events(
        self, s: Any, meeting_id: str, session_id: str, ingested: datetime, t0: datetime | None
    ) -> list[DomainEvent]:
        status = getattr(s, "track_status", None)
        if status is None or len(status) == 0:
            return []
        # FastF1 status codes: 1 clear, 2 yellow, 4 safety car, 5 red, 6/7 virtual safety car.
        code_to_type = {
            "2": EventType.YELLOW_FLAG_STARTED,
            "4": EventType.SAFETY_CAR_DEPLOYED,
            "5": EventType.RED_FLAG_STARTED,
            "6": EventType.SAFETY_CAR_DEPLOYED,
        }
        out: list[DomainEvent] = []
        for _, row in status.iterrows():
            et = code_to_type.get(str(row.get("Status")))
            if et is None:
                continue
            t = _rel_to_abs(t0, row.get("Time")) or ingested
            out.append(
                DomainEvent(
                    event_type=et,
                    source="fastf1",
                    event_time=t,
                    first_seen_at=t,
                    ingested_at=ingested,
                    meeting_id=meeting_id,
                    session_id=session_id,
                    payload={"status_code": str(row.get("Status"))},
                )
            )
        return out

    def _race_control_events(
        self, s: Any, meeting_id: str, session_id: str, ingested: datetime
    ) -> list[DomainEvent]:
        rcm = getattr(s, "race_control_messages", None)
        if rcm is None or len(rcm) == 0:
            return []
        out: list[DomainEvent] = []
        for _, row in rcm.iterrows():
            # Race-control messages carry absolute timestamps.
            t = _to_utc(row.get("Time")) or ingested
            out.append(
                DomainEvent(
                    event_type=EventType.RACE_CONTROL_MESSAGE_PUBLISHED,
                    source="fastf1",
                    event_time=t,
                    first_seen_at=t,
                    ingested_at=ingested,
                    meeting_id=meeting_id,
                    session_id=session_id,
                    payload={
                        "message": _str_or_none(row.get("Message")),
                        "category": _str_or_none(row.get("Category")),
                    },
                )
            )
        return out


def _int_or_none(v: Any) -> int | None:
    try:
        import pandas as pd

        if v is None or pd.isna(v):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _float_or_none(v: Any) -> float | None:
    try:
        import pandas as pd

        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        import pandas as pd

        return bool(pd.isna(v))
    except (TypeError, ValueError):  # pragma: no cover - non-scalar / unhashable input
        return False


def _str_or_none(v: Any) -> str | None:
    if _is_missing(v):
        return None
    text = str(v).strip()
    return text or None


def _slug(v: Any) -> str | None:
    s = _str_or_none(v)
    return s.lower().replace(" ", "_") if s else None
