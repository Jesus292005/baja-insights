import type { ChainLink, PitchPoint } from '../contracts/overlay';

/**
 * Turns the goal chain links (with v1.1 coordinates) into what the tactics board draws.
 * Rules from docs/aviso-cadena-coordenadas.md:
 * - Each link draws its own action from start to end; a recovery (end null) is a dot.
 * - A dotted line joins the ball between links that the chain does not cover, from the last link
 *   with the ball to the start of the next one. Off-ball runs are skipped: the runner never touches it.
 * - The dragged defender, if the run carries it, is an arrow of its own.
 * Only the players in the chain are drawn: there are no positions for the other 20.
 */

/** SVG units of the pitch drawing: 1050 × 680, y grows downwards. */
export const PITCH_W = 1050;
export const PITCH_H = 680;
export const toSvg = ([x, y]: PitchPoint): [number, number] => [x * 10, (68 - y) * 10];

export type PlayStep =
  | { kind: 'dot'; link: number; at: PitchPoint }
  | { kind: 'pass' | 'shot' | 'run' | 'other'; link: number; from: PitchPoint; to: PitchPoint; cross: boolean };

export interface GoalPlay {
  steps: PlayStep[];
  /** Ball moves the chain does not cover, e.g. from Cota's recovery to Salgado. */
  gaps: { from: PitchPoint; to: PitchPoint; before: number }[];
  defender: { name: string | null; from: PitchPoint; to: PitchPoint; link: number } | null;
  /** Where to write each player's name: the start of their action. */
  labels: { link: number; player: string; at: PitchPoint }[];
}

const isPoint = (p: unknown): p is PitchPoint =>
  Array.isArray(p) && p.length === 2 && typeof p[0] === 'number' && typeof p[1] === 'number';

/** True when every link carries a start, so the play can be drawn. Older orders fall back to the list. */
export const hasCoordinates = (links: readonly ChainLink[] | undefined): links is ChainLink[] =>
  !!links?.length && links.every((l) => isPoint(l.start));

export function buildGoalPlay(links: readonly ChainLink[]): GoalPlay {
  const ordered = links.map((l, i) => ({ l, i })).sort((a, b) => a.l.t_s - b.l.t_s || a.i - b.i);
  const steps: PlayStep[] = [];
  const gaps: GoalPlay['gaps'] = [];
  const labels: GoalPlay['labels'] = [];
  let defender: GoalPlay['defender'] = null;
  let ball: PitchPoint | null = null;

  for (const { l, i } of ordered) {
    const start = l.start as PitchPoint;
    const end = isPoint(l.end) ? l.end : null;
    labels.push({ link: i, player: l.player, at: start });

    if (l.type === 'off_ball_run') {
      if (end) steps.push({ kind: 'run', link: i, from: start, to: end, cross: false });
      if (isPoint(l.dragged_defender_start) && isPoint(l.dragged_defender_end)) {
        defender = { name: l.dragged_defender ?? null, from: l.dragged_defender_start, to: l.dragged_defender_end, link: i };
      }
      continue; // the runner never has the ball
    }

    if (ball && (ball[0] !== start[0] || ball[1] !== start[1])) gaps.push({ from: ball, to: start, before: i });

    if (!end) {
      steps.push({ kind: 'dot', link: i, at: start });
      ball = start;
    } else {
      const kind = l.type === 'pass' ? 'pass' : l.type === 'shot' ? 'shot' : 'other';
      steps.push({ kind, link: i, from: start, to: end, cross: l.cross === true });
      ball = end;
    }
  }
  return { steps, gaps, defender, labels };
}

/**
 * The part of the pitch the play happens in, as an SVG viewBox [x, y, w, h] with a fixed aspect,
 * so the board zooms in on the play instead of showing 105 m for a move in one third.
 * Pads by `margin` metres and stays inside the pitch where it can.
 */
export function playViewBox(play: GoalPlay, aspect = 1.5, margin = 5): [number, number, number, number] {
  const pts: PitchPoint[] = [];
  for (const st of play.steps) {
    if (st.kind === 'dot') pts.push(st.at);
    else pts.push(st.from, st.to);
  }
  for (const g of play.gaps) pts.push(g.from, g.to);
  if (play.defender) pts.push(play.defender.from, play.defender.to);
  if (!pts.length) return [0, 0, PITCH_W, PITCH_H];

  let x0 = Math.min(...pts.map((p) => p[0])) - margin;
  let x1 = Math.max(...pts.map((p) => p[0])) + margin;
  let y0 = Math.min(...pts.map((p) => p[1])) - margin;
  let y1 = Math.max(...pts.map((p) => p[1])) + margin;
  // Fix the aspect by growing the short side around the centre.
  if ((x1 - x0) / (y1 - y0) > aspect) {
    const h = (x1 - x0) / aspect;
    const cy = (y0 + y1) / 2;
    [y0, y1] = [cy - h / 2, cy + h / 2];
  } else {
    const w = (y1 - y0) * aspect;
    const cx = (x0 + x1) / 2;
    [x0, x1] = [cx - w / 2, cx + w / 2];
  }
  // Keep it inside the pitch (plus the goal) when it fits, shifting rather than shrinking.
  const shift = (lo: number, hi: number, min: number, max: number): [number, number] => {
    if (hi - lo >= max - min) return [lo, hi];
    if (lo < min) return [min, min + (hi - lo)];
    if (hi > max) return [max - (hi - lo), max];
    return [lo, hi];
  };
  [x0, x1] = shift(x0, x1, -2, 107);
  [y0, y1] = shift(y0, y1, -1, 69);
  return [x0 * 10, (68 - y1) * 10, (x1 - x0) * 10, (y1 - y0) * 10];
}
