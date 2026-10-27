import { PITCH_H, PITCH_W, crossControl, toSvg, type DrawnPlay } from './play';

/**
 * Where the names of a play go on the pitch (SVG units). Each name tries a few spots around its
 * player and takes the one that touches the least: other names first, then the dots and the lines
 * of the play, then the edge of the drawing. Text widths are estimated from the font sizes in
 * stage.css (.pl-label, .pl-label-rival), so a name keeps a small margin around it.
 */

export type Anchor = 'start' | 'middle' | 'end';
export interface Placement {
  /** Text position: x per `anchor`, y on the baseline. */
  x: number;
  y: number;
  anchor: Anchor;
}
interface Box { x: number; y: number; w: number; h: number }
type Point = [number, number];

/** Font size and average glyph width (in em) of each label style. */
const FONT = {
  player: { size: 26, em: 0.62 },
  rival: { size: 22, em: 0.66 },
  tag: { size: 20, em: 0.66 },
} as const;
/** Radius kept clear around each dot of the play: markers, ends of lines, the ball. */
const DOT_R = 20;
/** Gap between two names. */
const PAD = 6;
/** Drawing area of the pitch backdrop (its viewBox), minus a margin. */
const BOUNDS = { x0: -24, y0: -24, x1: PITCH_W + 24, y1: PITCH_H + 24 };

export function textBox(text: string, kind: keyof typeof FONT, p: Placement): Box {
  const { size, em } = FONT[kind];
  const w = text.length * size * em;
  const x = p.anchor === 'start' ? p.x : p.anchor === 'end' ? p.x - w : p.x - w / 2;
  return { x, y: p.y - size * 0.8, w, h: size * 1.05 };
}

/** Spots around a player at (x, y), in order of preference (the first ones are nearest). */
function candidates(x: number, y: number, kind: keyof typeof FONT): Placement[] {
  const size = FONT[kind].size;
  const spots: Placement[] = [];
  for (const d of [16, 30, 48, 70]) {
    const above = y - d;
    const below = y + d + size * 0.75;
    const side = y + size * 0.3;
    spots.push(
      { x: x + d, y: above, anchor: 'start' },
      { x: x - d, y: above, anchor: 'end' },
      { x: x + d, y: below, anchor: 'start' },
      { x: x - d, y: below, anchor: 'end' },
      { x: x + d + 4, y: side, anchor: 'start' },
      { x: x - d - 4, y: side, anchor: 'end' },
      { x, y: above - 4, anchor: 'middle' },
      { x, y: below + 4, anchor: 'middle' },
    );
  }
  return spots;
}

const overlaps = (a: Box, b: Box, pad = 0) =>
  a.x - pad < b.x + b.w && b.x - pad < a.x + a.w && a.y - pad < b.y + b.h && b.y - pad < a.y + a.h;

const hitsDot = (b: Box, [cx, cy]: Point, r: number) => {
  const nx = Math.max(b.x, Math.min(cx, b.x + b.w));
  const ny = Math.max(b.y, Math.min(cy, b.y + b.h));
  return (cx - nx) ** 2 + (cy - ny) ** 2 < r * r;
};

const inside = (b: Box, [px, py]: Point) => px > b.x && px < b.x + b.w && py > b.y && py < b.y + b.h;

/** Points along a line every few units, to test it against a box. */
function sample(from: Point, to: Point, control?: Point): Point[] {
  const len = Math.hypot(to[0] - from[0], to[1] - from[1]);
  const n = Math.max(2, Math.ceil(len / 8));
  const pts: Point[] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    if (control) {
      const u = 1 - t;
      pts.push([u * u * from[0] + 2 * u * t * control[0] + t * t * to[0], u * u * from[1] + 2 * u * t * control[1] + t * t * to[1]]);
    } else {
      pts.push([from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t]);
    }
  }
  return pts;
}

export interface PlayLabels {
  /** One per player label, by the link it belongs to. */
  players: Map<number, Placement>;
  defender: Placement | null;
  /** Minute tags of separate actions, by link (see DrawnPlay.tags). */
  tags: Map<number, Placement>;
}

/**
 * @param names Text of each player label, in the order of `drawn.labels`.
 * @param defenderText Text next to the dragged defender, if any.
 * @param tagTexts Text of each minute tag, in the order of `drawn.tags`.
 */
export function placeLabels(drawn: DrawnPlay, names: string[], defenderText: string | null, tagTexts: string[] = []): PlayLabels {
  const dots: Point[] = [];
  const lines: Point[][] = [];
  for (const st of drawn.steps) {
    if (st.kind === 'marker') {
      dots.push(toSvg(st.at));
      continue;
    }
    const a = toSvg(st.from);
    const b = toSvg(st.to);
    dots.push(a, b);
    lines.push(sample(a, b, st.cross ? crossControl(a, b) : undefined));
  }
  for (const g of drawn.gaps) lines.push(sample(toSvg(g.from), toSvg(g.to)));
  if (drawn.defender) {
    const a = toSvg(drawn.defender.from);
    const b = toSvg(drawn.defender.to);
    dots.push(a, b);
    lines.push(sample(a, b));
  }

  const placed: Box[] = [];
  const place = (text: string, kind: keyof typeof FONT, at: Point): Placement => {
    let best: Placement | null = null;
    let bestCost = Infinity;
    candidates(at[0], at[1], kind).forEach((c, i) => {
      const box = textBox(text, kind, c);
      let cost = i * 2;
      if (box.x < BOUNDS.x0 || box.y < BOUNDS.y0 || box.x + box.w > BOUNDS.x1 || box.y + box.h > BOUNDS.y1) cost += 2000;
      for (const p of placed) if (overlaps(box, p, PAD)) cost += 1000;
      for (const d of dots) if (hitsDot(box, d, DOT_R)) cost += 200;
      for (const line of lines) if (line.some((pt) => inside(box, pt))) cost += 120;
      if (cost < bestCost) {
        bestCost = cost;
        best = c;
      }
    });
    placed.push(textBox(text, kind, best!));
    return best!;
  };

  const players = new Map<number, Placement>();
  drawn.labels.forEach((l, i) => players.set(l.link, place(names[i] ?? '', 'player', toSvg(l.at))));
  const defender = drawn.defender && defenderText ? place(defenderText, 'rival', toSvg(drawn.defender.from)) : null;
  const tags = new Map<number, Placement>();
  drawn.tags.forEach((g, i) => tags.set(g.link, place(tagTexts[i] ?? '', 'tag', toSvg(g.at))));
  return { players, defender, tags };
}
