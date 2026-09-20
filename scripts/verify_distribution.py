from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="neuropace-wheel-") as directory:
        with zipfile.ZipFile(args.wheel) as wheel:
            assert not any(Path(name).name.startswith(".env") for name in wheel.namelist())
            wheel.extractall(directory)
        check = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
import neuropace
from neuropace.api.app import create_app, FRONTEND_DIST, DEMO_SCRIPT
from neuropace.config import Settings
from neuropace.doctor import FRONTEND_DIST as DOCTOR_DIST
assert Path(neuropace.__file__).is_relative_to(sys.argv[1])
assert (FRONTEND_DIST / 'index.html').is_file(), 'Installed wheel is missing the frontend'
assert DEMO_SCRIPT.is_file(), 'Installed wheel is missing the practice lecture'
assert FRONTEND_DIST == DOCTOR_DIST
assert (Path(sys.argv[1]) / 'mindwave' / 'macos_rfcomm.swift').is_file()
app = create_app(Settings(data_dir=Path(sys.argv[1]) / 'runtime', headset_port='sim', totem_port='keyboard', allow_offline_llm=True))
with TestClient(app) as client:
    assert client.get('/api/health').json()['ok']
    index = client.get('/session/new')
    assert index.status_code == 200 and 'assets/index-' in index.text
    for asset in (FRONTEND_DIST / 'assets').iterdir():
        response = client.get('/assets/' + asset.name)
        assert response.status_code == 200 and response.content == asset.read_bytes()
    lectures = client.get('/api/lectures').json()['lectures']
    assert any(lecture['id'] == 'lec_demo0001' and lecture['word_count'] > 700 for lecture in lectures)
app.state.db.close()
print('DISTRIBUTION PASS: isolated wheel serves SPA, assets, API and practice lecture; Swift helper included')
"""
        subprocess.run([sys.executable, "-I", "-c", check, directory], cwd=directory, check=True, timeout=30)


if __name__ == "__main__":
    main()
