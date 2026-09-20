import { activeLearnerId } from "../lib/activeLearner";
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation, useNavigate, useOutlet, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type { SessionPublic } from "../lib/types";
import { sessionTitle } from "../components/SessionSwitcher";
import SessionNavigation, { sessionHref, type SessionTab } from "../components/SessionNavigation";

export type LibraryTab = SessionTab;

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
  return value === "notes" || value === "review" || value === "replay" || value === "quiz" || value === "artifacts";
}

export function libraryHref(sessionId: string, tab: LibraryTab, inLibrary = true) {
  if (!inLibrary) return `/${tab}/${sessionId}`;
  return sessionHref(sessionId, tab);
}

function tabFromLocation(pathname: string, paramTab: string | undefined, queryTab: string | null): LibraryTab {
  if (isTab(paramTab)) return paramTab;
  if (isTab(queryTab)) return queryTab;
  const segment = pathname.split("/").filter(Boolean)[2];
  if (isTab(segment)) return segment;
  return "notes";
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

  return (
    <LibraryContext.Provider value={{ sessionId, tab, inLibrary }}>
      <div className={"library" + (tab === "replay" ? " library-replay" : "")}>
        <SessionNavigation sessionId={sessionId} tab={tab} title={title}
          sessions={sessions} titles={titles}
          onSelect={(id) => nav(sessionHref(id, tab))} />
        <div className="library-body">{metaError ? <div className="panel error">{metaError}</div> : children}</div>
      </div>
    </LibraryContext.Provider>
  );
}

/** Adds the same shell to legacy/team routes; sample renderers have no lecture to navigate. */
export function SessionRouteFrame({ tab, children, useOriginal = false }: { tab: LibraryTab; children: ReactNode; useOriginal?: boolean }) {
  const { sessionId = "" } = useParams();
  const [search] = useSearchParams();
  const lectureSessionId = useOriginal ? search.get("original") : sessionId;
  if (!lectureSessionId || lectureSessionId === "sample") return <>{children}</>;
  return <LibraryFrame sessionId={lectureSessionId} tab={tab}>{children}</LibraryFrame>;
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
