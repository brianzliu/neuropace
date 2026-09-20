import { useEffect, useState } from "react";
import { api, errorText } from "../lib/api";
import type { ManimContent } from "../lib/types";

/** A math animation (docs/PRODUCT.md §5a): rendered lazily on mount, since the render itself can take a
 * few seconds and the server may not have manim installed at all — either way the caption still reads on
 * its own, so this never leaves a blank board element. */
export default function ManimView({ c }: { c: ManimContent }) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setUrl(null);
    setErr(null);
    api
      .renderManim(c)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch((e) => {
        if (!cancelled) setErr(errorText(e));
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c.script, c.scene_name]);

  return (
    <div className="stack">
      {c.title ? <div className="label-2">{c.title}</div> : null}
      {url ? (
        <video className="oh-manim-video" src={url} controls autoPlay loop muted playsInline />
      ) : err ? (
        <div className="oh-manim-fallback label-3">Video unavailable ({err}). {c.caption}</div>
      ) : (
        <div className="oh-manim-fallback label-3">Rendering the animation…</div>
      )}
      {url && c.caption ? <div className="label-3">{c.caption}</div> : null}
    </div>
  );
}
