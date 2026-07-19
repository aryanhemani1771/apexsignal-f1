# DATA DICTIONARY

Canonical identifiers, timestamps, and core entities. Expanded as each phase lands real
schemas; Phase 0 defines the provenance timestamps and event envelope that everything else
builds on.

## Stable identifiers
| ID | Meaning | Example form |
|---|---|---|
| `season` | Championship year | `2024` |
| `event_round` | Round within a season | `10` |
| `meeting_id` | A Grand Prix weekend | `2024-10` |
| `session_id` | A session within a meeting | `2024-10-R` (R/Q/S/FP1…) |
| `driver_id` | Stable driver key | `VER`, `NOR` |
| `constructor_id` | Stable constructor key | `red_bull`, `mclaren` |
| `lap_id` | One driver-lap | `2024-10-R:VER:L34` |
| `stint_id` | One tyre stint | `2024-10-R:VER:S2` |
| `event_id` | UUID of a domain event | uuid4 |

## Provenance timestamps (on every observation / event)
| Field | Meaning | Used for |
|---|---|---|
| `event_time` | When the thing happened in the world | ordering / race clock |
| `published_at` | When a source published it (news/docs) | availability of external info |
| `first_seen_at` | When **we** first observed it | **backtest availability (authoritative)** |
| `ingested_at` | When it entered our store | ops/debug |
| `effective_at` | When an effect starts applying (e.g., penalty) | model parameter timing |

Rule: backtests and point-in-time features use `first_seen_at` (or a more defensible
timestamp) so no future information leaks. Leakage tests enforce it.

## Domain event envelope
Every event carries: `event_id` (UUID), `event_type`, `source`, `source_event_id?`,
`event_time`, `first_seen_at`, `ingested_at`, `meeting_id?`, `session_id?`, `driver_id?`,
`constructor_id?`, `payload` (dict), `schema_version` (int). Replaying the ordered event
log reproduces race state deterministically.

## Event types (initial set)
`LapCompleted, SectorCompleted, PositionChanged, PitEntry, PitExit, PitStopCompleted,
TyreCompoundChanged, YellowFlagStarted, SafetyCarDeployed, RedFlagStarted,
RaceControlMessagePublished, WeatherUpdated, DriverStopped, DriverRetired,
PenaltyAnnounced, NewsEventPublished, MarketBookUpdated, TradeObserved`.

## Contract types (pricing targets)
Driver win, podium, points finish, head-to-head (A ahead of B), retirement (DNF),
both constructor cars finish, safety car (race / next N laps), pit before lap N,
positions gained ≥ K, fastest lap, constructor points comparison. Contracts are only shown
when a real market maps to them with high confidence.
