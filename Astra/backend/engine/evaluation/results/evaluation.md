# ASTRA Synthetic Scenario Evaluation

Synthetic prototype metrics; not mission or clinical validation.

| Scenario | Lead time (days) | False alarm rate | Fault vs change accuracy | Expected | Observed |
|---|---:|---:|---:|---|---|
| normal |  | 0.0 |  | normal | normal |
| sleep_degradation | None | 0.0 |  | attention | normal |
| radiation_spike | 0 | 0.0 |  | urgent | urgent |
| gravity_transition | 0 | 0.0 |  | attention | attention |
| flatline_fault |  | 0.0 | 0.5 | sensor_fault | sensor_fault |
