"""Run Hub, Ground Station, and Link Simulator together on loopback."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ASTRA_ROOT", Path(__file__).resolve().parents[1]))
PROJECT = Path(os.environ.get("ASTRA_PROJECT") or (ROOT.parent if (ROOT.parent / "security").is_dir() else ROOT))
for package_path in ("", "engine", "link", "simulators", "ground-backend"):
    path = str(ROOT / package_path)
    if path not in sys.path: sys.path.insert(0, path)
for package_path in ("security", "ai-companion"):
    path = str(PROJECT / package_path)
    if path not in sys.path: sys.path.insert(0, path)
os.environ.setdefault("ASTRA_LINK_DB", str(ROOT / "hub" / "data" / "link.db"))

import yaml
import uvicorn
from astra_link import LinkQueue
from astra_link.app import create_app as create_link_app, http_forward
from astra_link.link_sim import LinkSimulator
from astra_ground.app import create_app as create_ground_app
from companion.main import app as companion_app
from hub.app import create_app as create_hub_app


def _seed_cumulative(astronaut_id: str) -> float:
    """Continue the dose history across restarts instead of dropping to zero."""
    try:
        from hub.store import HubStore
        store = HubStore()
        try:
            latest = store.latest_reading(astronaut_id, "cumulative_dose")
            return float(latest["value"]) if latest else 0.0
        finally:
            store.close()
    except Exception:
        return 0.0


async def _serve():
    with (ROOT / "config" / "ports.yaml").open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    ports = cfg["ports"]
    host = cfg["hosts"]["loopback"]
    queue = LinkQueue(os.environ["ASTRA_LINK_DB"])
    services = [
        uvicorn.Server(uvicorn.Config(create_hub_app(queue=queue), host=host, port=int(ports["hub"]))),
        uvicorn.Server(uvicorn.Config(create_ground_app(queue=queue), host=host, port=int(ports["ground-backend"]))),
        uvicorn.Server(uvicorn.Config(companion_app, host=host, port=int(ports["companion"]))),
        uvicorn.Server(uvicorn.Config(create_link_app(LinkSimulator(queue, http_forward)), host=host, port=int(ports["link-sim"]))),
    ]
    async def simulated_wearable_stream():
        from simulators.crew import synthetic_profiles
        from simulators.dosimeter import DosimeterSimulator
        from simulators.smartwatch import SmartwatchSimulator, post_readings
        streams = []
        dosimeters = []
        for index, profile in enumerate(synthetic_profiles()):
            baseline = profile.get("baseline", {})
            streams.append(SmartwatchSimulator(
                profile["astronaut_id"], dict(baseline),
                seed=int(profile["astronaut_id"].replace("A-", "")) * 10 + 7))
            dosimeter = DosimeterSimulator(profile["astronaut_id"], seed=101 + index * 17)
            dosimeter.cumulative = _seed_cumulative(profile["astronaut_id"])
            dosimeters.append(dosimeter)
        await asyncio.sleep(2)
        while True:
            for simulator in streams:
                await asyncio.to_thread(post_readings, simulator.generate())
            for dosimeter in dosimeters:
                batch = await asyncio.to_thread(dosimeter.generate, False, None, 30)
                await asyncio.to_thread(post_readings, batch["personal"] + batch["area_monitors"])
            await asyncio.sleep(30)

    wearable_task = asyncio.create_task(simulated_wearable_stream())
    try:
        await asyncio.gather(*(service.serve() for service in services))
    finally:
        wearable_task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await wearable_task
        queue.close()


def main():
    print("ASTRA demo services listening on loopback. Press Ctrl+C to stop.")
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_serve(), loop_factory=loop_factory)


if __name__ == "__main__": main()
