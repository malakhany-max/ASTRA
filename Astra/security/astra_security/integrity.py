"""Integrity verification and classification."""

from __future__ import annotations

import statistics

from nacl.signing import VerifyKey

from .config import plaus_get, sec_get
from .events import raise_security_event
from .keys import get_device
from .signing import verify_signature
from .store import get_store
from .util import b64d, is_valid_nonce, parse_iso

TRUSTED = "trusted"
SUSPECT_FAULT = "suspect_fault"
SUSPECT_TAMPER = "suspect_tamper"

_SEVERITY = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}


class _Accumulator:
    def __init__(self) -> None:
        self.reasons: list[str] = []
        self.checks = {
            "signature": True,
            "freshness": True,
            "plausibility": True,
            "sensor_health": True,
            "cross_sensor": True,
        }
        self.tamper: list[tuple[str, str, str]] = []
        self.fault: list[tuple[str, str, str]] = []

    def fail(self, check: str, reason: str) -> None:
        self.checks[check] = False
        self.reasons.append(reason)

    def tamper_flag(self, event_type: str, severity: str, reason: str, check: str) -> None:
        self.fail(check, reason)
        self.tamper.append((event_type, severity, reason))

    def fault_flag(self, event_type: str, severity: str, reason: str, check: str) -> None:
        self.fail(check, reason)
        self.fault.append((event_type, severity, reason))


def verify_and_classify(message: dict, context: dict | None = None) -> dict:
    """Verify + classify a signed reading. See module docstring."""
    context = dict(context or {})
    raise_events = context.get("raise_events", True)
    acc = _Accumulator()

    device_id = message.get("device_id") if isinstance(message, dict) else None
    astronaut_id = message.get("astronaut_id", "unknown") if isinstance(message, dict) else "unknown"

    row = None
    if not device_id:
        acc.tamper_flag("tampered_message", "high", "missing device_id", "signature")
    else:
        row = get_device(device_id)
        if row is None:
            acc.tamper_flag("unpaired_device", "high",
                            f"device not paired: {device_id}", "signature")
        elif row.get("revoked"):
            acc.tamper_flag("unpaired_device", "high",
                            f"device revoked: {device_id}", "signature")
        else:
            public_key = VerifyKey(b64d(row["public_key"]))
            if not verify_signature(message, public_key):
                event_type = context.get("attack") or "forged_signature"
                if event_type not in ("forged_signature", "tampered_message"):
                    event_type = "forged_signature"
                acc.tamper_flag(event_type, "critical",
                                "signature verification failed", "signature")

    authentic = acc.checks["signature"]

    store = get_store()
    nonce = message.get("nonce") if isinstance(message, dict) else None
    seq = message.get("seq") if isinstance(message, dict) else None
    ts = message.get("ts") if isinstance(message, dict) else None

    if authentic:
        if not is_valid_nonce(nonce):
            acc.tamper_flag("replay", "high", "missing or malformed nonce", "freshness")
        else:
            last_seq = store.get_seen_seq(device_id)
            if not isinstance(seq, int):
                acc.tamper_flag("replay", "high", "missing or non-integer seq", "freshness")
            elif last_seq is not None and seq <= last_seq:
                acc.tamper_flag("replay", "high",
                                f"non-increasing seq ({seq} <= {last_seq})", "freshness")

        if ts:
            try:
                delta = (parse_iso(ts) - parse_iso(context.get("now") or _now())).total_seconds()
            except Exception:
                delta = None
            if delta is None:
                acc.tamper_flag("clock_anomaly", "medium", "unparseable timestamp", "freshness")
            else:
                tolerance = float(sec_get("freshness.tolerance_seconds", 86400))
                future = float(sec_get("freshness.allow_future_seconds", 120))
                jump_warn = float(sec_get("freshness.clock_jump_warn_seconds", 900))
                if delta > future or abs(delta) > tolerance:
                    acc.tamper_flag("replay", "high",
                                    f"timestamp outside freshness window (delta={int(delta)}s)",
                                    "freshness")
                elif abs(delta) > jump_warn:
                    acc.reasons.append(f"clock jump advisory (delta={int(delta)}s)")
                    if raise_events:
                        raise_security_event("clock_anomaly", device_id, astronaut_id,
                                             time_window=[ts, _now()], severity="low",
                                             evidence={"delta_seconds": int(delta)})
        else:
            acc.tamper_flag("clock_anomaly", "medium", "missing timestamp", "freshness")

        if nonce and is_valid_nonce(nonce):
            if not store.add_nonce(nonce, device_id, ts):
                acc.tamper_flag("replay", "high", "nonce already seen", "freshness")
        if isinstance(seq, int):
            store.set_seen_seq(device_id, seq)
        _prune_nonces()

    metric = message.get("metric") if isinstance(message, dict) else None
    value = message.get("value") if isinstance(message, dict) else None
    spec = plaus_get(f"plausibility.{metric}") if metric else None
    previous = _previous_sample(store, device_id, metric, context)

    if spec:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            acc.fault_flag("implausible_value", "medium",
                           f"{metric}: non-numeric value", "plausibility")
        else:
            v = float(value)
            lo, hi = float(spec["min"]), float(spec["max"])
            if v < lo or v > hi:
                acc.fault_flag("implausible_value", "medium",
                               f"{metric}={v} outside plausible range [{lo}, {hi}]",
                               "plausibility")
            elif previous is not None and previous.get("value") is not None:
                rate_reason = _rate_of_change(metric, v, previous, spec)
                if rate_reason:
                    acc.fault_flag("implausible_value", "medium", rate_reason, "plausibility")
    elif metric:
        acc.reasons.append(f"unknown metric '{metric}' (plausibility skipped)")

    if spec and isinstance(value, (int, float)) and not isinstance(value, bool):
        samples = _window_samples(store, device_id, metric, context)
        window = [float(sample["value"]) for sample in samples if sample.get("value") is not None]
        window.append(float(value))
        reason = _sensor_health(metric, window)
        if reason:
            acc.fault_flag("sensor_fault_suspected", "medium", reason, "sensor_health")
        else:
            reason = _dropout_reason(samples, ts)
            if reason:
                acc.fault_flag("sensor_fault_suspected", "medium", reason, "sensor_health")

    cross = _cross_sensor(store, message, context)
    for reason, event_type, severity in cross:
        acc.fault_flag(event_type, severity, reason, "cross_sensor")

    if authentic and metric and isinstance(value, (int, float)) and not isinstance(value, bool):
        store.record_sample(device_id, metric, float(value), ts)

    if acc.tamper:
        classification = SUSPECT_TAMPER
    elif acc.fault:
        classification = SUSPECT_FAULT
    else:
        classification = TRUSTED

    if raise_events and classification != TRUSTED:
        _emit(acc, device_id, astronaut_id, ts, classification)

    return {
        "classification": classification,
        "reasons": acc.reasons,
        "checks": acc.checks,
    }


def _now() -> str:
    from .util import now_iso
    return now_iso()


def _prune_nonces() -> None:
    get_store().prune_nonces(
        int(sec_get("nonce_cache.max_entries", 200000)),
        float(sec_get("nonce_cache.ttl_seconds", 172800)),
    )


def _previous_sample(store, device_id, metric, context) -> dict | None:
    if "previous" in context:
        return context["previous"]
    if not device_id or not metric:
        return None
    samples = store.recent_samples(device_id, metric, limit=1)
    return samples[0] if samples else None


def _window(store, device_id, metric, context) -> list[float]:
    return [float(s["value"]) for s in _window_samples(store, device_id, metric, context)
            if s.get("value") is not None]


def _window_samples(store, device_id, metric, context) -> list[dict]:
    if "window" in context:
        return [sample for sample in context["window"] if isinstance(sample, dict)]
    if not device_id or not metric:
        return []
    limit = int(sec_get("sensor_health.window", 12))
    return store.recent_samples(device_id, metric, limit=limit)


def _dropout_reason(samples: list[dict], current_ts: str | None) -> str | None:
    """Detect a recent sampling gap much larger than this sensor's cadence."""
    timestamps = [sample.get("ts") for sample in samples if sample.get("ts")]
    if current_ts:
        timestamps.append(current_ts)
    try:
        instants = [parse_iso(timestamp) for timestamp in timestamps]
    except Exception:
        return None
    gaps = [(instants[i + 1] - instants[i]).total_seconds()
            for i in range(len(instants) - 1)]
    positive_gaps = [gap for gap in gaps if gap > 0]
    if len(positive_gaps) < 4:
        return None
    cadence = statistics.median(positive_gaps[:-1])
    latest_gap = positive_gaps[-1]
    factor = float(sec_get("sensor_health.dropout_gap_factor", 4))
    if cadence > 0 and latest_gap > cadence * factor:
        return (f"sensor dropout: latest gap {latest_gap:.1f}s > "
                f"{factor:g}x median cadence {cadence:.1f}s")
    return None


def _rate_of_change(metric: str, value: float, previous: dict, spec: dict) -> str | None:
    if not previous.get("ts"):
        return None
    try:
        dt_min = abs((parse_iso(_now()) - parse_iso(previous["ts"])).total_seconds()) / 60.0
    except Exception:
        return None
    if dt_min <= 0:
        return None
    max_rate = float(spec.get("max_rate_per_min", float("inf")))
    rate = abs(value - float(previous["value"])) / dt_min
    if rate > max_rate * 1.5:
        return (f"{metric} changed {rate:.1f}/min > limit {max_rate}/min "
                f"(previous={previous['value']})")
    return None


def _sensor_health(metric: str, window: list[float]) -> str | None:
    if metric == "cumulative_dose":
        return None
    if len(window) < 2:
        return None
    flatline_min = int(sec_get("sensor_health.flatline_min_samples", 6))
    drift_min = int(sec_get("sensor_health.drift_min_samples", 8))
    cv_threshold = float(sec_get("sensor_health.noise_cv_threshold", 0.6))

    tail = window[-flatline_min:]
    if metric not in {"dose_rate", "neutron_dose_rate"} and len(tail) >= flatline_min and len(set(tail)) == 1:
        return f"{metric} flatlined at {tail[0]} for {flatline_min} samples"

    if len(window) >= drift_min:
        seg = window[-drift_min:]
        diffs = [seg[i + 1] - seg[i] for i in range(len(seg) - 1)]
        if all(d > 0 for d in diffs) or all(d < 0 for d in diffs):
            span = abs(seg[-1] - seg[0])
            if span > 0:
                return f"{metric} drifting monotonically over {drift_min} samples"

    if len(window) >= 4:
        mean = statistics.fmean(window)
        if mean:
            cv = statistics.pstdev(window) / abs(mean)
            if cv > cv_threshold:
                return f"{metric} noisy (cv={cv:.2f} > {cv_threshold})"
    return None


def _cross_sensor(store, message: dict, context: dict) -> list[tuple[str, str, str]]:
    """Return a list of (reason, event_type, severity) cross-sensor findings."""
    findings: list[tuple[str, str, str]] = []
    if not isinstance(message, dict):
        return findings
    device_id = message.get("device_id")
    metric = message.get("metric")
    value = message.get("value")
    if not device_id or not isinstance(value, (int, float)) or isinstance(value, bool):
        return findings

    cfg = plaus_get("cross_sensor", {}) or {}
    high_activity = float(cfg.get("high_activity_threshold", 70))
    low_activity = float(cfg.get("low_activity_threshold", 15))

    if metric == "heart_rate":
        activity = _latest_metric(store, device_id, "activity_level", context)
        if activity is not None and activity < low_activity and value > 180:
            findings.append(
                (f"heart_rate={value} with low activity={activity} (cross-sensor mismatch)",
                 "implausible_value", "medium")
            )
    elif metric == "activity_level" and value > high_activity:
        hr = _latest_metric(store, device_id, "heart_rate", context)
        if hr is not None and hr < 40:
            findings.append(
                (f"high activity={value} with resting heart_rate={hr} (cross-sensor mismatch)",
                 "implausible_value", "medium")
            )

    if metric in ("dose_rate", "neutron_dose_rate") and message.get("source") == "dosimeter":
        area = _latest_metric(store, device_id, metric, context, source="area_monitor")
        if area is not None and area > 0:
            ratio = float(value) / area
            if ratio < 0.2 or ratio > 5.0:
                findings.append(
                    (f"personal dosimeter={value} vs area monitor={area} "
                     f"(ratio {ratio:.2f}; co-occurring, not causal)",
                     "dosimeter_mismatch", "high")
                )
    return findings


def _latest_metric(store, device_id, metric, context, source: str | None = None) -> float | None:
    key = f"cross:{metric}:{source}"
    if key in context:
        return context[key]
    samples = store.recent_samples(device_id, metric, limit=5)
    for sample in reversed(samples):
        if sample.get("value") is not None:
            return float(sample["value"])
    return None


def _emit(acc: _Accumulator, device_id: str, astronaut_id: str, ts: str, classification: str) -> None:
    flags = list(acc.tamper) + list(acc.fault)
    seen: set[tuple[str, str]] = set()
    for event_type, severity, reason in flags:
        key = (event_type, severity)
        if key in seen:
            continue
        seen.add(key)
        raise_security_event(
            event_type, device_id, astronaut_id,
            time_window=[ts, _now()] if ts else None,
            severity=severity,
            evidence={"reason": reason, "classification": classification},
        )
