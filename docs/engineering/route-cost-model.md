# Dynamic Route-Cost Model (Engineering Spec)

Status: proposed — weights unvalidated. Tune with real trip data (Phase 2).

## Cost function
cost(e) = w_time*time(e) + w_dist*distance(e) + w_surface*surface_penalty(e)
        + w_weather*weather_penalty(e) + w_incident*incident_penalty(e)
        + closure(e)

closure(e) = +inf if verified closure else 0

## Units
time: seconds; distance: metres; penalties: dimensionless, normalised 0..1.

## Default weight profiles
| profile | w_time | w_dist | w_surface | w_weather | w_incident |
|---|---|---|---|---|---|
| fastest | 1.0 | 0.05 | 0.1 | 0.1 | 0.2 |
| safest | 0.4 | 0.05 | 0.6 | 0.8 | 0.9 |
| cheapest | 0.5 | 0.5 | 0.2 | 0.2 | 0.3 |
| fuel | 0.3 | 0.6 | 0.4 | 0.2 | 0.2 |

Per-tenant overrides permitted; bounded to [0,2] with validation.

## Penalty functions
surface_penalty(e) = base_surface[e] * vehicle_factor(vehicle_class, surface_type)
  base_surface: paved=0, rough=0.3, unpaved=0.6, pothole_report=+0.2*confidence
  vehicle_factor: car=1.0, light_truck=1.2, hgv=1.5

weather_penalty(e) = f(condition_at_arrival, visibility, wind, flood_exposure)
  heavy_rain=0.8, flood_exposure=1.0 (capped), low_visibility=0.5, high_wind=0.4
  Evaluated at expected segment arrival time, not now (Section 6 rule).

incident_penalty(e) = sum over active incidents on e of
  severity_norm * confidence * age_decay(age)
  age_decay = exp(-age_hours / 24)
  Low-confidence (<0.3) reports capped at 0.1 and never set closure.

## Hard constraints
- Verified closure => infinite cost.
- Low-confidence data must never silently close a road.
- Unverified/stale reports carry reduced weight.

## Time-of-arrival weather
Route search computes cumulative time; for each edge, arrival_time = departure +
cumulative_time; weather looked up at arrival_time (interpolated from forecast).

## Explainability output (required in every route response)
cost_breakdown: [ {term, value, weight, contribution} ] per alternative, plus a
human-readable `explanation` string.

## Calibration plan
- Collect real trips (GPS traces + outcomes) from pilot tenants.
- Fit weights per profile via constrained optimisation; holdout validation.
- Acceptance: chosen route matches expert ranking >= 80% on pilot set.