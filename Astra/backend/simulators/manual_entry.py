"""Signed manual and clinical-entry helper."""

from hub import security_adapter as sec

_ALLOWED = {"bp_systolic": "mmHg", "bp_diastolic": "mmHg", "blood_glucose": "mg/dL"}


def make_manual_reading(astronaut_id: str, metric: str, value: float, unit: str | None = None,
                        source: str = "manual") -> dict:
    if metric not in _ALLOWED:
        raise ValueError(f"metric must be one of {', '.join(_ALLOWED)}")
    if source not in ("manual", "clinical_device"):
        raise ValueError("source must be manual or clinical_device")
    device_id = f"{source}-{astronaut_id.replace('-', '')}"
    reading = {"schema": "astra.reading.v1", "astronaut_id": astronaut_id,
               "metric": metric, "value": float(value), "unit": unit or _ALLOWED[metric],
               "source": source, "quality": 1.0}
    return sec.sign_reading(reading, device_id)
