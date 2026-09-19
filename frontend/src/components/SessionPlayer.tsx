import { useEffect, useRef, useState } from "react";
import { mmss } from "../lib/format";
import { Badge } from "./Badges";

interface Props {
  lectureId: string | null;
  hasMedia: boolean;
  duration: number | null;
  /** Called at 4 Hz with the current media time and whether it is playing. */
  onTime: (t: number, playing: boolean) => void;
  /** Increments whenever the backend asks to pause (pause_request). */
  pauseSeq: number;
  onResume?: () => void;
}

/** Recorded-lecture player: a <video> when media exists, else a virtual timer that drives the lecture clock. */
export default function SessionPlayer({ lectureId, hasMedia, duration, onTime, pauseSeq, onResume }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [vt, setVt] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [pausedByFlag, setPausedByFlag] = useState(false);
  const startRef = useRef<{ wall: number; t: number } | null>(null);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (hasMedia) {
        const v = videoRef.current;
        if (!v) return;
        const t = v.currentTime;
        const p = !v.paused && !v.ended;
        setVt(t);
        setPlaying(p);
        onTime(t, p);
      } else {
        let t = vt;
        if (playing && startRef.current) {
          t = startRef.current.t + (performance.now() - startRef.current.wall) / 1000;
          if (duration && t >= duration) {
            t = duration;
            setPlaying(false);
            startRef.current = null;
          }
          setVt(t);
        }
        onTime(t, playing);
      }
    }, 250);
    return () => window.clearInterval(id);
  }, [hasMedia, playing, vt, duration, onTime]);

  useEffect(() => {
    if (pauseSeq === 0) return;
    if (hasMedia) videoRef.current?.pause();
    else if (playing) {
      setVt((t) => (startRef.current ? startRef.current.t + (performance.now() - startRef.current.wall) / 1000 : t));
      setPlaying(false);
      startRef.current = null;
    }
    setPausedByFlag(true);
  }, [pauseSeq]); // eslint-disable-line react-hooks/exhaustive-deps

  const play = () => {
    setPausedByFlag(false);
    onResume?.();
    if (hasMedia) {
      void videoRef.current?.play();
    } else {
      startRef.current = { wall: performance.now(), t: vt };
      setPlaying(true);
    }
  };
  const pause = () => {
    if (hasMedia) videoRef.current?.pause();
    else {
      if (startRef.current) setVt(startRef.current.t + (performance.now() - startRef.current.wall) / 1000);
      setPlaying(false);
      startRef.current = null;
    }
  };

  return (
    <div className="player">
      {hasMedia && lectureId ? <video ref={videoRef} src={`/media/${lectureId}`} controls preload="auto" /> : null}
      {!hasMedia ? <span className="t-footnote label-2">virtual player (no media file): the transcript is revealed on this clock</span> : null}
      <span className="clock">
        {mmss(vt)}
        {duration ? ` / ${mmss(duration)}` : ""}
      </span>
      {playing ? (
        <button className="btn" onClick={pause}>
          Pause
        </button>
      ) : (
        <button className="btn btn-primary" onClick={play}>
          {pausedByFlag ? "Resume" : "Play"}
        </button>
      )}
      {pausedByFlag ? <Badge tone="accent">paused by a focus flag</Badge> : null}
    </div>
  );
}
