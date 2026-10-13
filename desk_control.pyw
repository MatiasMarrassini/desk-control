"""Lanzador sin consola de Desk Control (lo usa el arranque con Windows)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from widget.main import main  # noqa: E402

raise SystemExit(main(sys.argv[1:]))
