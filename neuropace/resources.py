from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
ASSETS = PACKAGE / "_assets"
FRONTEND_DIST = ASSETS / "frontend" if ASSETS.is_dir() else ROOT / "frontend" / "dist"
DEMO_SCRIPT = ASSETS / "demo.json" if ASSETS.is_dir() else ROOT / "data" / "lectures" / "demo" / "script.json"
