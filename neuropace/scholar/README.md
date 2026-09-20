# neuropace/scholar — scholarly sources for gap notes (OpenAlex)

A sidecar, not a change to the product's pipeline. After a lecture, each missed moment already gets a
note, a check question and re-teaching artifacts (`llm/artifacts.py`). This package adds, beside that
package and never inside it, up to three open-access papers from OpenAlex for the term the learner missed.

## Data

- **OpenAlex API** (`api.openalex.org`) for two calls per session: `/text/topics` labels the lecture with
  one of OpenAlex's ~4.5k topics (subfield › field › domain), and `/works?search=` finds open-access
  articles and reviews for each gap's query, constrained to that topic and, if nothing matches, to its
  field. Never unconstrained: an off-field paper that shares a word is worse than saying nothing.
- **OpenAlex snapshot on AWS Open Data** (`s3://openalex/data/jsonl/topics/`, https://registry.opendata.aws/openalex/)
  for `data/openalex_topics.json`: the whole topic table, compacted to id, name, keywords and the
  subfield/field/domain path. `scripts/fetch_openalex_topics.py` rebuilds it over plain HTTPS (no AWS
  account). It is the offline stand-in for `/text/topics` (`topics.classify_local`, keyword overlap) and
  is labelled `source: "local"` wherever it is used.

## Budget

OpenAlex meters requests. Keyless use gets ~$0.10/day (a works search costs $0.001, so about 100 gap
lookups); a free account key (`OPENALEX_API_KEY`) gets $1/day. Every response's `X-RateLimit-*` headers
are surfaced at `GET /api/scholar/status` and in each `/scholar` response. The cache (`data/scholar.db`,
its own SQLite file) means a session is fetched once, and two moments on the same term cost one search.

## Integration surface

- `app.include_router(scholar.router, prefix="/api")` in `api/app.py` — the only line touched elsewhere.
- Reads: `db.get_session`, `db.get_gaps`, `db.get_lecture(full=True)`, `db.get_words`.
- Writes: `data/scholar.db` only. Deleting it forgets fetched sources, nothing else.
- Frontend: `components/ScholarSources.tsx`, rendered by `views/Lecture.tsx` after the notes load.

## Routes

| Route | What |
|---|---|
| `GET /api/scholar/status` | key/mailto configured, topic table loaded, last-seen budget |
| `GET /api/sessions/{id}/scholar[?refresh=1]` | references per gap, lecture topic, budget, attribution |
| `GET /api/lectures/{id}/scholar/topics[?refresh=1]` | the lecture's OpenAlex topic label |

Each gap row carries `source`: `openalex`, `cache`, `empty` (nothing in topic or field), `unavailable`
(network or budget; `error` says which), `disabled` (`NEUROPACE_SCHOLAR=off`). The UI shows the
unavailable and empty cases in words rather than hiding the strip.

## Query per gap

The note's `key_term` when a model wrote the notes, plus lecture key terms actually said in the span (or
just before it); otherwise the span's most repeated content words. The extractive offline stand-in's
`key_term` is positional, not semantic, so it is not used (`package_source: "offline"`).

## Jargon density (content-based risk, PLAN Part III Tier 1)

`jargon.py` scores a transcript from the words alone, against `data/term_specificity.json.gz`: for each
stemmed term, how concentrated its use is in one field of science across every English abstract in a
`works` slice (KL divergence of the term's field distribution from the corpus's, normalised so a term
exclusive to its home field scores 1). A 20 s window's score is the mean specificity of its distinct content
words; a window is flagged when it is ≥1.5σ above the *same lecture's* other windows and has at least four
scored terms. Flagged windows merge into spans with the terms that drove them, so the flag is explainable.

Build the table with `scripts/build_jargon_table.py` (stdlib only, multiprocess, reads Voloridge's
`fetch.py` output layout or any `updated_date=*/part_*.gz` tree). The bundled table was built 2026-09-20
from 32 part files (5.2 GB, 5.18M works, 641k with an English abstract and a topic; only ~9% of works
qualify) in 2.5 minutes on a laptop: 59k terms with df ≥ 20, 0.56 MB gzipped. Rebuilding is a
coffee-break job on a decent connection, no EC2 needed:

```bash
# any ~30 mid-sized part files; scripts/build_jargon_table.py reads whatever is under data/openalex/works
python3 src/openalex/fetch.py --entity works --max-files 30 --max-size-gb 8      # Voloridge's fetcher, or curl
uv run python scripts/build_jargon_table.py --workers 7
```

`GET /api/scholar/status` reports the table's size and `dev_sized` (true under 200k usable works).

Check: `GET /api/lectures/lec_demo0001/scholar/jargon` — the practice lecture's planted segment 3 must be
`rank: 1` and hold the strongest span (`tests/test_scholar.py` asserts this against whatever table is
bundled). Routes: `/api/lectures/{id}/scholar/jargon`, `/api/sessions/{id}/scholar/jargon`
(`?window=20&step=5&z=1.5`). The notes page shows the spans as "Where the lecture got dense", beside the
sensor-flagged moments, not merged with them: wiring this in as a third flag source is a separate decision.

## Not done (deliberately)

No LLM call is made here; the one-line "why" under each paper is the abstract's first sentence. No
outcome claim is attached to sources or to jargon spans; if one is ever wanted, it needs the yoked-control
design in `PLAN.md` Part I §9. Jargon spans are not fed into `merge_into_gaps` yet.
