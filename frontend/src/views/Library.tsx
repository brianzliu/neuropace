import { activeLearnerId } from "../lib/activeLearner";
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useOutlet, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type { SessionPublic } from "../lib/types";
import { BackLink } from "../components/BackLink";

export type LibraryTab = "notes" | "review" | "replay" | "quiz";

const TABS: { id: LibraryTab; label: string }[] = [
  { id: "notes", label: "Notes" },
  { id: "review", label: "Review" },
  { id: "replay", label: "Replay" },
  { id: "quiz", label: "Quiz" },
];

interface LibraryContextValue {
  sessionId: string;
  tab: LibraryTab;
  inLibrary: boolean;
}

const LibraryContext = createContext<LibraryContextValue | null>(null);

export function useLibrary() {
  return useContext(LibraryContext);
}

function isTab(value: string | null | undefined): value is LibraryTab {
  return value === "notes" || value === "review" || value === "replay" || value === "quiz";
}

export function libraryHref(sessionId: string, tab: LibraryTab, inLibrary = true) {
  if (!inLibrary) return `/${tab}/${sessionId}`;
  return `/library/${sessionId}/${tab}`;
}

function tabFromLocation(pathname: string, paramTab: string | undefined, queryTab: string | null): LibraryTab {
  if (isTab(paramTab)) return paramTab;
  if (isTab(queryTab)) return queryTab;
  const segment = pathname.split("/").filter(Boolean)[2];
  if (isTab(segment)) return segment;
  return "notes";
}

function sessionTitle(session: SessionPublic, titles: Record<string, string>) {
  if (session.lecture_id && titles[session.lecture_id]) return titles[session.lecture_id];
  if (session.mode === "office_hours") return "Office Hours";
  return session.mode === "recorded" ? "Recorded lecture" : "Live session";
}

function sessionMeta(session: SessionPublic) {
  return new Date(session.started_at * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function useLibraryIndex() {
  const [sessions, setSessions] = useState<SessionPublic[] | null>(null);
  const [titles, setTitles] = useState<Record<string, string>>({});
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const learnerId = await activeLearnerId();
        const [listed, lectures] = await Promise.all([
          api.sessions({ learner_id: learnerId }),
          api.lectures().catch(() => ({ lectures: [] as { id: string; title: string }[] })),
        ]);
        if (cancelled) return;
        setSessions(listed.sessions.filter(s => s.mode !== "review" && s.mode !== "office_hours"));
        setTitles(Object.fromEntries(lectures.lectures.map((l) => [l.id, l.title])));
      } catch {
        if (!cancelled) setSessions([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return { sessions, titles };
}

export function LibraryFrame({ sessionId, tab, children }: { sessionId: string; tab: LibraryTab; children: ReactNode }) {
  const { sessions, titles } = useLibraryIndex();
  const [session, setSession] = useState<SessionPublic | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const loc = useLocation();
  const nav = useNavigate();
  const inLibrary = loc.pathname.startsWith("/library");

  useEffect(() => {
    let cancelled = false;
    setSession(null);
    setMetaError(null);
    if (!sessionId) return;
    api
      .session(sessionId)
      .then((s) => {
        if (!cancelled) setSession(s);
      })
      .catch((e) => {
        if (!cancelled) setMetaError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const title = session ? sessionTitle(session, titles) : sessionId ? "Session" : "Library";
  const known = !!sessions?.some((s) => s.id === sessionId);
  const showQuiz = !session || !!session.lecture_id;

  return (
    <LibraryContext.Provider value={{ sessionId, tab, inLibrary }}>
      <div className={"library" + (tab === "replay" ? " library-replay" : "")}>
        <div className="library-head" style={{ display: "flex", flexWrap: "wrap", gap: ".6rem", alignItems: "center", justifyContent: "space-between", marginBottom: ".6rem" }}>
          <div className="row" style={{ gap: ".6rem" }}>
            <BackLink to="/lectures" label="Back to Lectures" />
            <h1 className="library-title" style={{ margin: 0, fontSize: "1.35rem" }}>
              {title}
            </h1>
            <span className="muted small mono">{sessionId}</span>
          </div>
          <div className="row" style={{ gap: ".6rem" }}>
            {sessions && sessions.length ? (
              <label className="small muted">
                <span className="visually-hidden">Choose session</span>
                <select value={known ? sessionId : ""} onChange={(e) => { if (e.target.value) nav(libraryHref(e.target.value, tab, inLibrary)); }}>
                  {!known && sessionId ? <option value="">{title}</option> : null}
                  {sessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {sessionTitle(s, titles)}, {sessionMeta(s)}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
        </div>
        <nav className="library-tabs" aria-label="Session sections">
          {TABS.map((t) => {
            if (t.id === "quiz" && !showQuiz) return null;
            const active = t.id === tab;
            return (
              <Link
                key={t.id}
                to={libraryHref(sessionId, t.id, inLibrary)}
                className={"library-tab" + (active ? " active" : "")}
                aria-current={active ? "page" : undefined}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
        <div className="library-body">{metaError ? <div className="panel error">{metaError}</div> : children}</div>
      </div>
    </LibraryContext.Provider>
  );
}

export default function Library() {
  const params = useParams();
  const [search] = useSearchParams();
  const loc = useLocation();
  const outlet = useOutlet();
  const sessionId = params.sessionId ?? "";
  const tab = tabFromLocation(loc.pathname, params.tab, search.get("tab"));

  if (!sessionId) {
    return <Navigate to="/lectures" replace />;
  }
  if (!outlet) {
    return <Navigate to={libraryHref(sessionId, tab)} replace />;
  }
  return (
    <LibraryFrame sessionId={sessionId} tab={tab}>
      {outlet}
    </LibraryFrame>
  );
}
