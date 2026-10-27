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
