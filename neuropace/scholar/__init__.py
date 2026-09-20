"""Scholarly sources for gap notes, backed by OpenAlex (a sidecar; see README.md in this package).

Nothing here is imported by the session, gap or review code. The only integration point is
`app.include_router(scholar.router, prefix="/api")` in api/app.py; everything else is read-only over the
existing store and writes to its own cache file.
"""

from .routes import router

__all__ = ["router"]
