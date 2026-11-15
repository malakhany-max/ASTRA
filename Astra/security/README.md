# ASTRA Security, Link, and Attack Simulator

These components run locally and can be exercised without a hub, ground service,
or external network. They use the shared contracts in `contracts/` and the
demo-only thresholds in `config/`.

## Run the attack evaluation

From the repository root:

```powershell
python -m attack_sim run --attack all
```

The CLI prints a compact table followed by a JSON evaluation report. To run one
scenario, replace `all` with one of `forged_signature`, `replay`,
`spoofed_device`, `tampered_in_transit`, `timestamp_manipulation`,
`dosimeter_fake_spike`, `dosimeter_false_all_clear`, or
`flatline_sensor_fault`. The report includes per attack detection,
classification, reasons, latency, security event creation, and captured uplink
envelopes, plus aggregate detection and benign-control false-positive rates.
All scenarios call the SDK directly and replace the uplink sink with an
in-memory capture; they do not contact a live endpoint.

Hub integrations can call `attack_sim.trigger_scenario(name)` or import a
specific `attack_sim.attack_<scenario>` function. These functions return the
same per-scenario result for a hub route such as `POST /demo/scenario` to wrap.

`sign_envelope()` automatically encrypts `exposure_record` and `history_bundle`
payloads before signing. A trusted receiver should call
`verify_envelope()` and then `decrypt_envelope_payload()`; both sides need the
shared master key configured through the keyring or `ASTRA_MASTER_KEY`.

For a pinned local HTTPS Ground endpoint, set `ASTRA_GROUND_UPLINK_URL` to its
HTTPS URL and `ASTRA_GROUND_TLS_CERT_SHA256` to the certificate's SHA-256
fingerprint (hex, colons optional). HTTPS forwarding fails closed when the pin
is absent or does not match. The default local URL uses HTTP.

## Run tests and security checks

```powershell
python -m pytest
bandit -r security/astra_security link/astra_link attack_sim -x '*/tests/*'
pip-audit -r requirements.txt --no-deps --disable-pip
```

On Windows, pytest's FastAPI `TestClient` uses a local loopback socket pair;
some restricted shells block that socket even though the app runs in-process.
Run the test command in an environment that permits local loopback. The Link
queue and attack simulator unit tests do not need an external network.

## Threat model (STRIDE)

| Threat | Example | Controls in this slice |
|---|---|---|
| Spoofing | Unpaired device claims an astronaut identity | Setup-time pinned Ed25519 keys; signed readings and envelopes; offline trust store |
| Tampering | Reading changed in transit or database row altered | Ed25519 signatures; canonical JSON; append-only audit hash chain; AES-GCM fields |
| Repudiation | Operator denies a sensitive action | Signed audit entries and security events |
| Information disclosure | Health or psychological data leaves the hub without consent | Consent tiers; raw audio filtering; field encryption; hashed event evidence |
| Denial of service | Link flood, oversized envelope, or link outage | Message-size cap; per-node priority-aware rate limit; priority-aware SlowAPI submit limit; SlowAPI limits on control/state endpoints; bounded SQLite queue; retry backoff |
| Elevation of privilege | Astronaut invokes crew-wide or command permission | Role matrix, Argon2 password hashes, short-lived JWTs, FastAPI permission dependency, audit records |

## Residual risks and limits

- All physiological and radiation thresholds are explicitly `DEMO_ONLY`; they
  are not clinical or mission-qualified limits.
- This repository slice does not include the Ground Backend. Ground must verify
  envelope signatures before accepting queued messages and decrypt sensitive
  payloads only after verification.
- Link forwarding defaults to local HTTP. Configure the certificate pin and
  HTTPS Ground URL when deployment requires TLS.
- Offline revocation only takes effect after a valid signed revocation bundle
  reaches and is applied by the hub.
- The simulator's false-positive rate is measured against one benign control
  reading. It is an evaluation smoke metric, not a statistical field estimate.
- This workspace has been exercised under Python 3.13. Run the same suite under
  the project's target Python 3.11 before release.
