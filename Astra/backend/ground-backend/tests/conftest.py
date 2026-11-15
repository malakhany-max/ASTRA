import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ground-backend"))
sys.path.insert(0, str(ROOT / "hub"))
sys.path.insert(0, str(ROOT / "simulators"))
sys.path.insert(0, str(ROOT / "link"))
sys.path.insert(0, str(ROOT.parent / "security"))
