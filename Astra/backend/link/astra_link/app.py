"""Link Simulator HTTP API (port 8300).

Run:  uvicorn astra_link.app:create_app --factory --port 8300
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import http.client
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .link_sim import LinkSimulator
from .queue import LinkQueue

GROUND_URL = os.environ.get("ASTRA_GROUND_UPLINK_URL", "http://127.0.0.1:8100/uplink")
GROUND_TLS_CERT_SHA256 = os.environ.get("ASTRA_GROUND_TLS_CERT_SHA256", "")
HUB_DOWNLINK_URL = os.environ.get("ASTRA_HUB_DOWNLINK_URL", "http://127.0.0.1:8000/internal/downlink")
HUB_TLS_CERT_SHA256 = os.environ.get("ASTRA_HUB_TLS_CERT_SHA256", "")


def http_forward(envelope: dict) -> bool:
    """Deliver one envelope to the Ground Backend.

    True  = delivered, or permanently rejected by Ground (4xx): do not retry.
    False = transient failure (5xx / connection error): retry with backoff.
    """
    body = json.dumps(envelope).encode("utf-8")
    target_url = HUB_DOWNLINK_URL if envelope.get("direction") == "downlink" else GROUND_URL
    target_pin = HUB_TLS_CERT_SHA256 if envelope.get("direction") == "downlink" else GROUND_TLS_CERT_SHA256
    parsed = urlsplit(target_url)
    try:
        if parsed.scheme == "https":
            if not target_pin:
                return False
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with http.client.HTTPSConnection(
                parsed.hostname, parsed.port or 443, timeout=5, context=context,
            ) as conn:
                conn.connect()
                certificate = conn.sock.getpeercert(binary_form=True) if conn.sock else b""
                if not _certificate_matches_pin(certificate, target_pin):
                    return False
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                status = response.status
                response.read()
                return 200 <= status < 300 or 400 <= status < 500

        req = urllib.request.Request(
            target_url, data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        return 400 <= exc.code < 500
    except Exception:
        return False


def _certificate_matches_pin(certificate: bytes, expected_pin: str) -> bool:
    """Compare a SHA-256 certificate fingerprint to a configured hex pin."""
    pin = re.sub(r"[^0-9a-f]", "", expected_pin.lower())
    if len(pin) != 64 or not certificate:
        return False
    return hmac.compare_digest(hashlib.sha256(certificate).hexdigest(), pin)


class DelayBody(BaseModel):
    seconds: float = Field(ge=0, le=3600)


async def _pump_loop(sim: LinkSimulator, interval: float) -> None:
    while True:
        with contextlib.suppress(Exception):
            await asyncio.to_thread(sim.pump)
        await asyncio.sleep(interval)


async def _mark_priority_one(request: Request) -> None:
    """Parse the small submit body before SlowAPI so P1 can bypass its quota."""
    try:
        envelope = await request.json()
    except Exception:
        envelope = None
    request.state.priority_one = (
        isinstance(envelope, dict)
        and isinstance(envelope.get("priority"), int)
        and not isinstance(envelope.get("priority"), bool)
        and envelope["priority"] == 1
    )


def create_app(sim: LinkSimulator | None = None, pump_interval: float = 0.5) -> FastAPI:
    if sim is None:
        sim = LinkSimulator(LinkQueue(), http_forward)
    limiter = Limiter(key_func=get_remote_address, default_limits=[])

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_pump_loop(app.state.sim, pump_interval))
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="ASTRA Link Simulator", lifespan=lifespan)
    app.add_middleware(CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:4173", "http://127.0.0.1:4174",
                       "http://localhost:5173", "http://localhost:5174", "http://localhost:4173", "http://localhost:4174"],
        allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"])
    app.state.sim = sim
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/link/state")
    @limiter.limit("120/minute")
    def link_state(request: Request):
        return app.state.sim.state()

    @app.post("/link/connect")
    @limiter.limit("120/minute")
    def link_connect(request: Request):
        app.state.sim.connect()
        app.state.sim.queue.set_meta("demo_scenario", "restore_link")
        return app.state.sim.state()

    @app.post("/link/disconnect")
    @limiter.limit("120/minute")
    def link_disconnect(request: Request):
        app.state.sim.disconnect()
        app.state.sim.queue.set_meta("demo_scenario", "cut_link")
        return app.state.sim.state()

    @app.post("/link/delay")
    @limiter.limit("120/minute")
    def link_delay(request: Request, body: DelayBody):
        app.state.sim.set_delay(body.seconds)
        app.state.sim.queue.set_meta("demo_scenario", "link_delay")
        return app.state.sim.state()

    @app.post("/link/submit", dependencies=[Depends(_mark_priority_one)])
    @limiter.limit(
        "120/minute",
        exempt_when=lambda request: bool(getattr(request.state, "priority_one", False)),
    )
    async def link_submit(request: Request):
        try:
            envelope = await request.json()
        except Exception:
            return JSONResponse({"accepted": False, "reason": "invalid JSON"}, status_code=400)
        res = app.state.sim.submit(envelope)
        if res["accepted"]:
            return JSONResponse(res, status_code=202)
        reason = res.get("reason", "")
        code = 413 if "large" in reason else 429 if "rate" in reason else 400
        return JSONResponse(res, status_code=code)

    return app
