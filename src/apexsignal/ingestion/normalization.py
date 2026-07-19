"""Normalization helpers and data-quality checks over a domain-event log.

The quality report surfaces the integrity problems the build spec calls out (duplicate laps,
impossible lap ordering, tyre-age decreasing without a change, out-of-range positions, pit
ordering, backward timestamps, implausible weather). It is deterministic and offline.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from pydantic import BaseModel

from apexsignal.domain.events import DomainEvent, EventType, sort_key

MAX_PLAUSIBLE_POSITION = 30
PLAUSIBLE_TRACK_TEMP_C = (-5.0, 70.0)
PLAUSIBLE_AIR_TEMP_C = (-10.0, 55.0)


class QualityIssue(BaseModel):
    severity: str  # "error" | "warning"
    code: str
    message: str
    driver_id: str | None = None
    lap: int | None = None


class DataQualityReport(BaseModel):
    events_checked: int
    issues: list[QualityIssue]

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def summary(self) -> str:
        return (
            f"checked {self.events_checked} events: "
            f"{self.n_errors} error(s), {self.n_warnings} warning(s)"
        )


def run_quality_checks(events: Iterable[DomainEvent]) -> DataQualityReport:
    """Run all data-quality checks over an event log."""
    raw = list(events)
    ordered = sorted(raw, key=sort_key)
    issues: list[QualityIssue] = []

    # Monotonicity is checked on the AS-GIVEN order so genuinely out-of-order source data is
    # detected; the remaining checks run on the canonical replay order.
    _check_timestamp_monotonic(raw, issues)
    _check_laps(ordered, issues)
    _check_pit_ordering(ordered, issues)
    _check_weather(ordered, issues)

    return DataQualityReport(events_checked=len(ordered), issues=issues)


def _check_timestamp_monotonic(events: list[DomainEvent], issues: list[QualityIssue]) -> None:
    prev = None
    for e in events:
        if prev is not None and e.event_time < prev:
            issues.append(
                QualityIssue(
                    severity="error",
                    code="timestamp_backward",
                    message=f"event_time {e.event_time.isoformat()} precedes prior event",
                )
            )
        prev = e.event_time


def _check_laps(events: list[DomainEvent], issues: list[QualityIssue]) -> None:
    seen_laps: dict[str, set[int]] = defaultdict(set)
    last_lap: dict[str, int] = {}
    last_tyre_age: dict[str, int] = {}

    for e in events:
        if e.event_type in (EventType.PIT_STOP_COMPLETED, EventType.TYRE_COMPOUND_CHANGED):
            if e.driver_id is not None:
                last_tyre_age[e.driver_id] = 0  # a fresh set resets the age baseline
            continue
        if e.event_type is not EventType.LAP_COMPLETED or e.driver_id is None:
            continue

        did = e.driver_id
        lap = e.payload.get("lap")
        position = e.payload.get("position")
        lap_time = e.payload.get("lap_time")
        tyre_age = e.payload.get("tyre_age")

        if isinstance(lap, int):
            if lap in seen_laps[did]:
                issues.append(
                    QualityIssue(
                        severity="error",
                        code="duplicate_lap",
                        message=f"duplicate lap {lap}",
                        driver_id=did,
                        lap=lap,
                    )
                )
            seen_laps[did].add(lap)
            if did in last_lap and lap < last_lap[did]:
                issues.append(
                    QualityIssue(
                        severity="error",
                        code="lap_out_of_order",
                        message=f"lap {lap} follows lap {last_lap[did]}",
                        driver_id=did,
                        lap=lap,
                    )
                )
            last_lap[did] = max(last_lap.get(did, lap), lap)

        if isinstance(position, int) and not (1 <= position <= MAX_PLAUSIBLE_POSITION):
            issues.append(
                QualityIssue(
                    severity="error",
                    code="position_out_of_range",
                    message=f"position {position} outside 1..{MAX_PLAUSIBLE_POSITION}",
                    driver_id=did,
                    lap=lap if isinstance(lap, int) else None,
                )
            )

        if isinstance(lap_time, int | float) and lap_time <= 0:
            issues.append(
                QualityIssue(
                    severity="error",
                    code="nonpositive_lap_time",
                    message=f"lap_time {lap_time} is not positive",
                    driver_id=did,
                )
            )

        if isinstance(tyre_age, int):
            if did in last_tyre_age and tyre_age < last_tyre_age[did]:
                issues.append(
                    QualityIssue(
                        severity="warning",
                        code="tyre_age_decreased",
                        message=(
                            f"tyre_age {tyre_age} < {last_tyre_age[did]} without a tyre change"
                        ),
                        driver_id=did,
                        lap=lap if isinstance(lap, int) else None,
                    )
                )
            last_tyre_age[did] = tyre_age


def _check_pit_ordering(events: list[DomainEvent], issues: list[QualityIssue]) -> None:
    in_pit: dict[str, bool] = defaultdict(bool)
    for e in events:
        if e.driver_id is None:
            continue
        if e.event_type is EventType.PIT_ENTRY:
            in_pit[e.driver_id] = True
        elif e.event_type is EventType.PIT_EXIT:
            if not in_pit[e.driver_id]:
                issues.append(
                    QualityIssue(
                        severity="error",
                        code="pit_exit_before_entry",
                        message="pit exit without a matching pit entry",
                        driver_id=e.driver_id,
                    )
                )
            in_pit[e.driver_id] = False


def _check_weather(events: list[DomainEvent], issues: list[QualityIssue]) -> None:
    for e in events:
        if e.event_type is not EventType.WEATHER_UPDATED:
            continue
        track = e.payload.get("track_temp")
        air = e.payload.get("air_temp")
        if isinstance(track, int | float) and not (
            PLAUSIBLE_TRACK_TEMP_C[0] <= track <= PLAUSIBLE_TRACK_TEMP_C[1]
        ):
            issues.append(
                QualityIssue(
                    severity="warning",
                    code="track_temp_implausible",
                    message=f"track_temp {track}C outside plausible range",
                )
            )
        if isinstance(air, int | float) and not (
            PLAUSIBLE_AIR_TEMP_C[0] <= air <= PLAUSIBLE_AIR_TEMP_C[1]
        ):
            issues.append(
                QualityIssue(
                    severity="warning",
                    code="air_temp_implausible",
                    message=f"air_temp {air}C outside plausible range",
                )
            )
