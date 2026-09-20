import { useMemo } from "react";
import rough from "roughjs/bin/rough";
import type { Options } from "roughjs/bin/core";

const generator = rough.generator();

/** Hand-drawn primitives (docs/PRODUCT.md §5a): the board should read as a whiteboard, not a UI panel, so
 * every box/line on it is sketchy roughjs output rendered as plain SVG paths — no canvas, no DOM refs. */
function Paths({ drawable, className }: { drawable: ReturnType<typeof generator.rectangle>; className?: string }) {
  const paths = useMemo(() => generator.toPaths(drawable), [drawable]);
  return (
    <g className={className}>
      {paths.map((p, i) => (
        <path key={i} d={p.d} stroke={p.stroke} strokeWidth={p.strokeWidth} fill={p.fill || "none"} />
      ))}
    </g>
  );
}

export function RoughRect({ x, y, w, h, options, className }: { x: number; y: number; w: number; h: number; options?: Options; className?: string }) {
  const drawable = useMemo(() => generator.rectangle(x, y, w, h, options), [x, y, w, h, options]);
  return <Paths drawable={drawable} className={className} />;
}

export function RoughEllipse({ x, y, w, h, options, className }: { x: number; y: number; w: number; h: number; options?: Options; className?: string }) {
  const drawable = useMemo(() => generator.ellipse(x + w / 2, y + h / 2, w, h, options), [x, y, w, h, options]);
  return <Paths drawable={drawable} className={className} />;
}

export function RoughLine({ x1, y1, x2, y2, options, className }: { x1: number; y1: number; x2: number; y2: number; options?: Options; className?: string }) {
  const drawable = useMemo(() => generator.line(x1, y1, x2, y2, options), [x1, y1, x2, y2, options]);
  return <Paths drawable={drawable} className={className} />;
}

export function RoughArrowhead({ x, y, angle, size = 26, options, className }: { x: number; y: number; angle: number; size?: number; options?: Options; className?: string }) {
  const drawable = useMemo(() => {
    const back = angle + Math.PI;
    const a1 = back - 0.45;
    const a2 = back + 0.45;
    return generator.linearPath(
      [
        [x + size * Math.cos(a1), y + size * Math.sin(a1)],
        [x, y],
        [x + size * Math.cos(a2), y + size * Math.sin(a2)],
      ],
      options,
    );
  }, [x, y, angle, size, options]);
  return <Paths drawable={drawable} className={className} />;
}
