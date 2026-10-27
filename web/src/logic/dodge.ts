import { clock, surname } from '../i18n/strings';
import { placeLabels, textBox } from './labels';
import { VIEW_BOX, buildPlay, crossControl, orientPlay, toSvg, type MatchPlay } from './play';

/**
 * Cinema mode draws the play on the pitch behind the cards, so each card goes where it covers the
 * least of it. Everything here is in canvas pixels (the 1920 × 1080 stage).
 */

export interface Box { x: number; y: number; w: number; h: number }
type Point = [number, number];

const CANVAS = { w: 1920, h: 1080 };
/** Safe area of the canvas (5% margins), where the cards live. */
const SAFE = { x0: 96, y0: 54, x1: 1824, y1: 1026 };

/** The pitch SVG (viewBox, preserveAspectRatio meet) mapped onto the canvas. */
const k = Math.min(CANVAS.w / VIEW_BOX.w, CANVAS.h / VIEW_BOX.h);
const ox = (CANVAS.w - VIEW_BOX.w * k) / 2;
const oy = (CANVAS.h - VIEW_BOX.h * k) / 2;
export const svgToCanvas = ([x, y]: Point): Point => [ox + (x - VIEW_BOX.x) * k, oy + (y - VIEW_BOX.y) * k];

function along(a: Point, b: Point, control?: Point): Point[] {
  const n = Math.max(2, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 12));
  return Array.from({ length: n + 1 }, (_, i) => {
    const t = i / n;
    if (!control) return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    const u = 1 - t;
    return [u * u * a[0] + 2 * u * t * control[0] + t * t * b[0], u * u * a[1] + 2 * u * t * control[1] + t * t * b[1]];
  });
}

/** Points of the play as drawn (lines, marks and names), in canvas pixels. */
export function playPoints(play: MatchPlay): Point[] {
  const drawn = buildPlay(orientPlay(play), true);
  const pts: Point[] = [];
  for (const st of drawn.steps) {
    if (st.kind === 'marker') {
      pts.push(toSvg(st.at));
      continue;
    }
    const a = toSvg(st.from);
    const b = toSvg(st.to);
    pts.push(...along(a, b, st.cross ? crossControl(a, b) : undefined));
  }
  for (const g of drawn.gaps) pts.push(...along(toSvg(g.from), toSvg(g.to)));
  if (drawn.defender) pts.push(...along(toSvg(drawn.defender.from), toSvg(drawn.defender.to)));
  // Names and minute tags, where PlayLayer writes them.
  const names = drawn.labels.map((l) => surname(l.player));
  const tags = drawn.tags.map((g) => clock(g.t_s));
  const spots = placeLabels(drawn, names, null, tags);
  const boxes = [
    ...drawn.labels.map((l, i) => textBox(names[i], 'player', spots.players.get(l.link)!)),
    ...drawn.tags.map((g, i) => textBox(tags[i], 'tag', spots.tags.get(g.link)!)),
  ];
  for (const b of boxes) for (const fx of [0, 0.5, 1]) for (const fy of [0, 1]) pts.push([b.x + b.w * fx, b.y + b.h * fy]);
  return pts.map(svgToCanvas);
}

const overlap = (a: Box, b: Box) =>
  Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));

export interface CardToPlace {
  key: string;
  /** Where the card goes by default (its slot, or the goal dock): wins a tie. */
  home: Box;
  /** Only these places, instead of the grid of spots (for a bar that spans the canvas). */
  only?: Box[];
}

/** Just below the score bug and the cinema badge, for cards too wide to sit beside them. */
const BELOW_TOP = 170;

/** Spots a card of that size can take: three columns by four rows of the safe area. */
function spots(w: number, h: number): { x: number; y: number }[] {
  const xs = [SAFE.x0, (CANVAS.w - w) / 2, SAFE.x1 - w];
  const ys = [SAFE.y0, BELOW_TOP, (CANVAS.h - h) / 2, SAFE.y1 - h];
  return xs.flatMap((x) => ys.map((y) => ({ x: Math.max(SAFE.x0, x), y: Math.max(SAFE.y0, y) })));
}

/**
 * Picks a spot per card, in order: the one covering the fewest points of the play, never on the
 * boxes already taken (the score bug, a fixed bottom bar, the cards placed before it). Among spots
 * that cover the same, the one nearest the card's default place wins.
 */
export function placeCards(cards: CardToPlace[], points: Point[], taken: Box[]): Map<string, Box> {
  const out = new Map<string, Box>();
  const busy = [...taken];
  for (const c of cards) {
    let best: Box = c.home;
    let bestCost = Infinity;
    const options = c.only ?? [c.home, ...spots(c.home.w, c.home.h).map((s) => ({ ...s, w: c.home.w, h: c.home.h }))];
    for (const box of options) {
      const { w, h } = box;
      const covered = points.reduce((n, [px, py]) => n + (px >= box.x && px <= box.x + w && py >= box.y && py <= box.y + h ? 1 : 0), 0);
      const clash = busy.reduce((a, b) => a + overlap(box, b), 0);
      const cost = covered * 10 + clash * 0.5 + (Math.abs(box.x - c.home.x) + Math.abs(box.y - c.home.y)) * 0.01;
      if (cost < bestCost) {
        bestCost = cost;
        best = box;
      }
    }
    out.set(c.key, best);
    busy.push(best);
  }
  return out;
}
