import hashlib

from astra_link import app as app_module


def test_tls_pin_checks_sha256_fingerprint():
    certificate = b"test certificate bytes"
    pin = hashlib.sha256(certificate).hexdigest()
    assert app_module._certificate_matches_pin(certificate, pin)
    assert app_module._certificate_matches_pin(certificate, ":".join(pin[i:i + 2] for i in range(0, 64, 2)))
    assert not app_module._certificate_matches_pin(certificate, "0" * 64)
    assert not app_module._certificate_matches_pin(b"", pin)


def test_https_forward_fails_closed_without_a_certificate_pin(monkeypatch):
    monkeypatch.setattr(app_module, "GROUND_URL", "https://ground.invalid/uplink")
    monkeypatch.setattr(app_module, "GROUND_TLS_CERT_SHA256", "")
    assert app_module.http_forward({"msg_id": "test"}) is False
