"""Scholar sidecar (neuropace/scholar): OpenAlex references under gap notes, without the network."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from neuropace.scholar import topics as topictable
from neuropace.scholar.cache import ScholarCache
from neuropace.scholar.openalex import (
    OpenAlexClient,
    OpenAlexUnavailable,
    first_sentence,
    parse_work,
    rank_works,
    reconstruct_abstract,
)
from neuropace.scholar.service import ScholarService, gap_query

SPAN = (
    "so the learning rate is the step size gradient descent takes each update and if it is too big the loss "
    "diverges and if it is too small training crawls which is why people use a learning rate schedule"
)


def _work(
    i: int, title: str, cited: int, rel: float, kind: str = "article", abstract: str | None = None
) -> dict:
    inv = None
    if abstract:
        inv = {}
        for p, tok in enumerate(abstract.split()):
            inv.setdefault(tok, []).append(p)
    return {
        "id": f"https://openalex.org/W{i}",
        "title": title,
        "publication_year": 2000 + i,
        "cited_by_count": cited,
        "doi": f"https://doi.org/10.1/{i}",
        "type": kind,
        "open_access": {"is_oa": True, "oa_url": f"https://oa.example/{i}.pdf"},
        "primary_location": {
            "landing_page_url": f"https://pub.example/{i}",
            "source": {"display_name": "Venue"},
        },
        "authorships": [{"author": {"display_name": f"Author {i}"}}, {"author": {"display_name": "B"}}],
        "abstract_inverted_index": inv,
        "topics": [{"id": "https://openalex.org/T10320"}],
        "relevance_score": rel,
    }


TOPIC_RESPONSE = {
    "meta": {"count": 1},
    "primary_topic": {
        "id": "https://openalex.org/T10320",
        "display_name": "Neural Networks and Applications",
        "score": 0.9,
        "subfield": {"display_name": "Artificial Intelligence"},
        "field": {"id": "https://openalex.org/fields/17", "display_name": "Computer Science"},
        "domain": {"display_name": "Physical Sciences"},
    },
    "topics": [],
}
WORKS_RESPONSE = {
    "meta": {"count": 3},
    "results": [
        _work(
            1,
            "Gradient-based learning applied to document recognition",
            59000,
            1600.0,
            abstract="Multilayer neural networks trained with back-propagation are the best example of gradient learning. More.",
        ),
        _work(2, "A novel learning rate schedule", 44, 800.0, abstract="We propose a schedule."),
        _work(3, "Unrelated but cited", 5000, 20.0),
    ],
}


class Recorder:
    """A fake OpenAlex transport: answers from fixtures, counts calls, can be switched off."""

    def __init__(self, down: bool = False) -> None:
        self.calls: list[str] = []
        self.down = down

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        if self.down:
            raise httpx.ConnectError("no network")
        headers = {
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Remaining": "900",
            "X-RateLimit-Remaining-USD": "0.09",
        }
        if request.url.path == "/text/topics":
            return httpx.Response(200, json=TOPIC_RESPONSE, headers=headers)
        if request.url.path == "/works":
            return httpx.Response(200, json=WORKS_RESPONSE, headers=headers)
        return httpx.Response(404, json={"error": "nope"})

    def client(self) -> OpenAlexClient:
        return OpenAlexClient(
            mailto="test@example.org", http=httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        )


def _session_with_gaps(db, n: int = 2):
    lr = db.create_learner("Ana")
    sess = db.create_session(learner_id=lr["id"], lecture_id="lec_demo0001", mode="recorded")
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": f"gap_{i}",
                "ord": i,
                "t_start": 10.0 * i,
                "t_end": 10.0 * i + 8,
                "span_text": SPAN,
                "flag_ids": [],
                "package": {
                    "note": {
                        "key_term": "learning rate",
                        "definition": "",
                        "connection": "",
                        "what_was_said": "",
                    }
                },
                "package_source": "llm",
                "status": "open",
            }
        )
    db.replace_gaps(sess["id"], rows)
    return sess


# ---------------------------------------------------------------- pure pieces
def test_abstract_round_trip_and_first_sentence():
    inv = {"Second": [2], "First": [0], "sentence.": [1], "one": [3], "here.": [4]}
    assert reconstruct_abstract(inv) == "First sentence. Second one here."
    assert first_sentence("Short. This is the real first sentence of the abstract. Then more.") == (
        "Short. This is the real first sentence of the abstract."
    )
    assert first_sentence("") == ""


def test_rank_works_prefers_relevance_then_citations_and_drops_far_matches():
    works = [parse_work(r) for r in WORKS_RESPONSE["results"]]
    ranked = rank_works(works, 3)
    assert [w.id for w in ranked] == ["W1", "W2"]  # W3: relevance 20/1600 < 10% of the best match
    d = ranked[0].as_dict()
    assert d["url"] == "https://oa.example/1.pdf" and d["authors"] == ["Author 1", "B"]
    assert d["why"].startswith("Multilayer neural networks")


def test_gap_query_uses_note_term_then_keyterms_then_content_words():
    gap = {"span_text": SPAN, "package": {"note": {"key_term": "learning rate"}}, "package_source": "llm"}
    assert gap_query(gap, ["gradient descent", "photosynthesis"]) == "learning rate gradient descent"
    # the extractive stand-in's key term is positional ("shouting"), so only the lecture's own terms are used
    offline = {"span_text": SPAN, "package": {"note": {"key_term": "shouting"}}, "package_source": "offline"}
    assert gap_query(offline, ["gradient descent"]) == "gradient descent"
    # a term said just before the span still anchors it
    ctx = {"span_text": "so that is why", "context_text": "the pseudorange is", "package_source": "offline"}
    assert gap_query(ctx, ["pseudorange"]) == "pseudorange"
    bare = {"span_text": SPAN, "package": None}
    q = gap_query(bare, [])
    assert "learning" in q or "rate" in q


def test_local_topic_table_is_bundled_and_lands_in_the_right_subfield():
    assert topictable.available() and topictable.load()["count"] > 4000
    top = topictable.classify_local(
        "gradient descent updates the weights of a neural network; the learning rate sets the step size; "
        "backpropagation, deep learning, momentum"
    )
    assert top and top[0].id == "T10320"
    assert topictable.classify_local("hello") == []


# ---------------------------------------------------------------- service + cache
async def test_service_fetches_once_then_serves_cache(settings, db):
    sess = _session_with_gaps(db, n=2)
    rec = Recorder()
    svc = ScholarService(settings, db, client=rec.client(), cache=ScholarCache(settings.data_dir / "s.db"))
    out = await svc.session_references(sess["id"])
    assert out["topics"]["source"] == "openalex" and out["topics"]["topics"][0]["id"] == "T10320"
    assert len(out["gaps"]) == 2
    g0, g1 = out["gaps"]
    assert g0["source"] == "openalex" and [i["id"] for i in g0["items"]] == ["W1", "W2"]
    assert g1["source"] == "cache"  # same term, same lecture: the query cache answered, no second search
    assert rec.calls.count("/works") == 1 and rec.calls.count("/text/topics") == 1
    assert out["budget"]["remaining"] == 900

    again = await svc.session_references(sess["id"])
    assert rec.calls.count("/works") == 1  # gap rows cached
    assert [g["source"] for g in again["gaps"]] == ["openalex", "cache"]
    await svc.aclose()


async def test_service_discloses_unavailable_and_falls_back_to_local_topics(settings, db):
    sess = _session_with_gaps(db, n=1)
    rec = Recorder(down=True)
    svc = ScholarService(settings, db, client=rec.client(), cache=ScholarCache(settings.data_dir / "s.db"))
    out = await svc.session_references(sess["id"])
    assert out["gaps"][0]["source"] == "unavailable" and out["gaps"][0]["items"] == []
    assert "openalex" in (out["gaps"][0]["error"] or "")
    # the topic label still comes from the bundled table, and says so
    assert out["topics"]["source"] in ("local", "unavailable")
    if out["topics"]["topics"]:
        assert out["topics"]["source"] == "local"

    # once the network is back, a plain call retries the unavailable rows without refresh
    rec.down = False
    out2 = await svc.session_references(sess["id"])
    assert out2["gaps"][0]["source"] == "openalex" and len(out2["gaps"][0]["items"]) == 2
    await svc.aclose()


async def test_service_respects_disabled_switch(settings, db, monkeypatch):
    monkeypatch.setenv("NEUROPACE_SCHOLAR", "off")
    sess = _session_with_gaps(db, n=1)
    rec = Recorder()
    svc = ScholarService(settings, db, client=rec.client(), cache=ScholarCache(settings.data_dir / "s.db"))
    out = await svc.session_references(sess["id"])
    assert out["gaps"][0]["source"] == "disabled" and rec.calls == []
    await svc.aclose()


async def test_search_widens_topic_to_field_but_never_unconstrained(settings, db):
    """Nothing inside the topic -> retry inside the field -> nothing there -> "empty", not off-field papers."""
    sess = _session_with_gaps(db, n=1)
    filters: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/text/topics":
            return httpx.Response(200, json=TOPIC_RESPONSE)
        flt = request.url.params.get("filter", "")
        filters.append(flt)
        if "topics.field.id:fields/17" in flt:
            return httpx.Response(200, json=WORKS_RESPONSE)
        return httpx.Response(200, json={"meta": {"count": 0}, "results": []})

    client = OpenAlexClient(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    svc = ScholarService(settings, db, client=client, cache=ScholarCache(settings.data_dir / "s.db"))
    out = await svc.session_references(sess["id"])
    assert [("topics.id:T10320" in f, "topics.field.id:fields/17" in f) for f in filters] == [
        (True, False),
        (False, True),
    ]
    assert out["gaps"][0]["source"] == "openalex" and len(out["gaps"][0]["items"]) == 2
    await svc.aclose()


async def test_client_raises_on_budget_exhausted():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "budget"}, headers={"X-RateLimit-Remaining": "0"})

    c = OpenAlexClient(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(OpenAlexUnavailable):
        await c.search_works("anything")
    assert c.budget.remaining == 0


# ---------------------------------------------------------------- routes (no change to the main router)
def test_routes_mounted_and_gap_packages_untouched(app, db):
    sess = _session_with_gaps(db, n=1)
    rec = Recorder()
    app.state.scholar = ScholarService(
        app.state.settings,
        app.state.db,
        client=rec.client(),
        cache=ScholarCache(app.state.settings.data_dir / "s.db"),
    )
    with TestClient(app) as tc:
        st = tc.get("/api/scholar/status").json()
        assert st["topic_table"]["available"] is True
        r = tc.get(f"/api/sessions/{sess['id']}/scholar")
        assert r.status_code == 200
        body = r.json()
        assert body["gaps"][0]["items"][0]["title"].startswith("Gradient-based")
        assert "OpenAlex" in body["attribution"]
        assert tc.get("/api/sessions/nope/scholar").status_code == 404
        # the notes route and the stored package are exactly what they were
        notes = tc.get(f"/api/sessions/{sess['id']}/notes").json()
        assert "references" not in json.dumps(notes)
    assert db.get_gaps(sess["id"])[0]["package"] == {
        "note": {"key_term": "learning rate", "definition": "", "connection": "", "what_was_said": ""}
    }


# ---------------------------------------------------------------- jargon (content-based risk from the transcript)
def test_jargon_tokeniser_matches_the_build_script():
    """The table is only valid if runtime and builder normalise words identically."""
    import importlib.util
    from pathlib import Path

    from neuropace.scholar import jargon

    spec = importlib.util.spec_from_file_location(
        "build_jargon_table", Path(__file__).resolve().parents[1] / "scripts" / "build_jargon_table.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    for w in [
        "Pseudorange,",
        "(ionospheric)",
        "satellites",
        "learning",
        "dual-frequency",
        "3D",
        "x",
        "-ish",
        "analyses.",
    ]:
        assert jargon.normalise_token(w) == mod.normalise_token(w), w


def test_jargon_flags_the_planted_dense_segment_of_the_practice_lecture(db):
    """PRD §10: segment 3 is deliberately dense. From the transcript alone it must rank first and hold the
    strongest flagged span. (Runs against whatever table is bundled; a dev-sized one is enough for this.)"""
    from neuropace.scholar import jargon

    if not jargon.available():
        pytest.skip("no term_specificity table bundled")
    lec = db.get_lecture("lec_demo0001", full=True)
    out = jargon.analyze(lec["words"], segments=lec["segments"])
    planted = [s for s in out["segments"] if s["planted_bad"]]
    assert len(planted) == 1 and planted[0]["rank"] == 1
    assert out["spans"], "no dense span flagged at all"
    strongest = max(out["spans"], key=lambda s: s["peak_z"])
    p = planted[0]
    assert p["t_start"] <= strongest["t_start"] and strongest["t_end"] <= p["t_end"] + 5.0
    assert any(t["term"] in ("multipath", "ionospheric") for t in strongest["terms"])
    assert out["table"]["available"] and "OpenAlex" in out["attribution"]


def test_jargon_analyze_without_table_or_words_is_empty_and_disclosed(monkeypatch):
    from neuropace.scholar import jargon

    monkeypatch.setattr(jargon, "load", lambda: None)
    out = jargon.analyze([{"w": "hello", "start": 0, "end": 1}])
    assert out["table"] == {"available": False} and out["spans"] == [] and out["windows"] == []


def test_jargon_routes(app):
    from neuropace.scholar import jargon

    with TestClient(app) as tc:
        st = tc.get("/api/scholar/status").json()
        assert "jargon_table" in st
        r = tc.get("/api/lectures/lec_demo0001/scholar/jargon")
        assert r.status_code == 200
        body = r.json()
        if jargon.available():
            assert body["segments"] and body["windows"]
        assert tc.get("/api/lectures/nope/scholar/jargon").status_code == 404
        assert tc.get("/api/sessions/nope/scholar/jargon").status_code == 404
