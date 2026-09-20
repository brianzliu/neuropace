import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from neuropace import manim_render
from neuropace.llm.prompts import office_hours_instructions
from neuropace.llm.schemas import ManimAnimation

GOOD_SCRIPT = """from manim import *

class TestScene(Scene):
    def construct(self):
        c = Circle()
        self.play(Create(c))
        self.wait(0.5)
"""


def test_manim_animation_accepts_a_well_formed_scene():
    m = ManimAnimation(title="t", caption="  a   circle  ", scene_name="TestScene", script=GOOD_SCRIPT)
    assert m.scene_name == "TestScene"
    assert m.caption == "a circle"


@pytest.mark.parametrize(
    "bad_script",
    [
        GOOD_SCRIPT + "\nimport os\n",
        GOOD_SCRIPT.replace("from manim import *", "from manim import *\nimport subprocess"),
        GOOD_SCRIPT.replace("from manim import *", "import requests\nfrom manim import *"),
        "x" * 5000,  # over length cap, and not a valid scene either
    ],
)
def test_manim_animation_rejects_unsafe_or_oversized_scripts(bad_script):
    with pytest.raises(ValidationError):
        ManimAnimation(title="t", caption="c", scene_name="TestScene", script=bad_script)


def test_manim_animation_requires_scene_name_to_match_a_defined_class():
    with pytest.raises(ValidationError):
        ManimAnimation(title="t", caption="c", scene_name="OtherScene", script=GOOD_SCRIPT)


def test_manim_animation_requires_construct_method():
    no_construct = GOOD_SCRIPT.replace("def construct(self):", "def draw(self):")
    with pytest.raises(ValidationError):
        ManimAnimation(title="t", caption="c", scene_name="TestScene", script=no_construct)


def test_office_hours_instructions_mentions_manim_only_when_enabled():
    on = office_hours_instructions(True)
    off = office_hours_instructions(False)
    assert "manim" in on and "scene_name" in on
    assert "manim" not in off
    assert "@@" not in on and "@@" not in off


@pytest.mark.asyncio
async def test_render_raises_manim_unavailable_when_not_installed(tmp_path, monkeypatch):
    from neuropace.config import Settings

    monkeypatch.setattr(manim_render, "manim_available", lambda: False)
    s = Settings(data_dir=tmp_path)
    s.ensure_dirs()
    with pytest.raises(manim_render.ManimUnavailable):
        await manim_render.render(s, GOOD_SCRIPT, "TestScene")


def test_manim_render_route_rejects_unsafe_script(app):
    with TestClient(app) as c:
        r = c.post(
            "/api/manim/render",
            json={"title": "t", "caption": "c", "scene_name": "TestScene", "script": GOOD_SCRIPT + "\nimport os\n"},
        )
        assert r.status_code == 400


def test_manim_render_route_503s_when_unavailable(app, monkeypatch):
    async def fake_render(*a, **k):
        raise manim_render.ManimUnavailable("no manim here")

    monkeypatch.setattr(manim_render, "render", fake_render)
    with TestClient(app) as c:
        r = c.post(
            "/api/manim/render",
            json={"title": "t", "caption": "c", "scene_name": "TestScene", "script": GOOD_SCRIPT},
        )
        assert r.status_code == 503
