"""Config loading. config.json (next to the repo root) overrides config.default.json."""
import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):  # PyInstaller exe: config lives next to the exe
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config.default.json"
USER_PATH = ROOT / "config.json"


def load() -> dict:
    cfg = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    if USER_PATH.exists():
        cfg.update(json.loads(USER_PATH.read_text(encoding="utf-8")))
    else:
        USER_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    cfg["output_dir"] = str(Path(cfg["output_dir"]).expanduser())
    cfg["audio_dir"] = str(Path(cfg["audio_dir"]).expanduser())
    Path(cfg["output_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["audio_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg
