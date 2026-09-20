/** Brain mascot stop-motion. Each sheet holds 6 frames in a single row;
 *  CSS steps(6) walks them. Adjacent copy always carries the meaning, so
 *  the animation itself is hidden from assistive tech. With reduced
 *  motion the first frame simply stands still. */
const ART = {
  /** Waving hello — empty states and greetings. */
  wave: "mascot-wave",
  /** Mid-jump cheer — cleared queues and wins. */
  cheer: "mascot-cheer",
  /** Growing thought bubbles — loading and organizing. */
  think: "mascot-think",
} as const;

export type MascotArt = keyof typeof ART;

export default function BrainMascot({ art, size = 72 }: { art: MascotArt; size?: number }) {
  return <div className={`mascot ${ART[art]}`} aria-hidden="true" style={{ width: size }} />;
}
