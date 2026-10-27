import type { ChainLink, OverlayOrder, PitchPoint } from '../contracts/overlay';
import { invisibleAssistPlayer } from '../contracts/overlay';
import type { PlayEvent } from '../data/match';
import type { Roster } from '../data/roster';

/**
 * Plays drawn on the full pitch: the goal chains (v1.1 coordinates) and the events other graphics
 * cite as evidence. Drawing rules from docs/aviso-cadena-coordenadas.md:
 * - Each action draws from its start to its end. Recoveries, tackles, duels and pressures are markers.
 * - In a goal chain, a dotted ball line joins links the chain does not cover, skipping off-ball runs:
 *   the runner never touches the ball.
 * - The dragged defender, if the run carries it, is an arrow of its own.
 * Only the players in the play are drawn: the engine has no positions for anyone else.
 */

export const PITCH_W = 1050;
export const PITCH_H = 680;
/** Pitch metres (origin bottom-left) to the 1050 × 680 SVG (y grows downwards). */
export const toSvg = ([x, y]: PitchPoint): [number, number] => [x * 10, (68 - y) * 10];

export type Side = 'home' | 'away';
export type MarkerKind = 'recovery' | 'duel' | 'pressure';
export type LegendKind = 'pass' | 'cross' | 'shot' | 'ball' | 'run' | 'defender' | MarkerKind;

/** A link of a play, with the side of the team that made it (for its colour). */
export interface PlayLink extends ChainLink {
  side: Side;
}

export type PlayStep =
  | { kind: 'marker'; marker: MarkerKind; link: number; at: PitchPoint }
  | { kind: 'pass' | 'shot' | 'run'; link: number; from: PitchPoint; to: PitchPoint; cross: boolean };

export interface DrawnPlay {
  steps: PlayStep[];
  gaps: { from: PitchPoint; to: PitchPoint; before: number }[];
  defender: { name: string | null; from: PitchPoint; to: PitchPoint; link: number } | null;
  labels: { link: number; player: string; at: PitchPoint }[];
  /** What the legend needs to explain, in a fixed order. */
  legend: LegendKind[];
}

const LEGEND_ORDER: LegendKind[] = ['pass', 'cross', 'shot', 'ball', 'run', 'defender', 'recovery', 'duel', 'pressure'];
const MARKERS: Record<string, MarkerKind> = { recovery: 'recovery', tackle: 'duel', duel: 'duel', pressure: 'pressure', foul: 'duel' };

const isPoint = (p: unknown): p is PitchPoint =>
  Array.isArray(p) && p.length === 2 && typeof p[0] === 'number' && typeof p[1] === 'number';

/** True when every link carries a start, so the play can be drawn. */
export const hasCoordinates = (links: readonly ChainLink[] | undefined): links is ChainLink[] =>
  !!links?.length && links.every((l) => isPoint(l.start));

export function buildPlay(links: readonly ChainLink[], connectBall: boolean): DrawnPlay {
  const ordered = links.map((l, i) => ({ l, i })).sort((a, b) => a.l.t_s - b.l.t_s || a.i - b.i);
  const steps: PlayStep[] = [];
  const gaps: DrawnPlay['gaps'] = [];
  const labels: DrawnPlay['labels'] = [];
  const legend = new Set<LegendKind>();
  let defender: DrawnPlay['defender'] = null;
  let ball: PitchPoint | null = null;

  for (const { l, i } of ordered) {
    if (!isPoint(l.start)) continue;
    const start = l.start;
    const end = isPoint(l.end) ? l.end : null;
    // One label per player, at their first action: three recoveries by Torres say "Torres" once.
    if (!labels.some((x) => x.player === l.player)) labels.push({ link: i, player: l.player, at: start });

    if (l.type === 'off_ball_run') {
      if (end) {
        steps.push({ kind: 'run', link: i, from: start, to: end, cross: false });
        legend.add('run');
      }
      if (isPoint(l.dragged_defender_start) && isPoint(l.dragged_defender_end)) {
        defender = { name: l.dragged_defender ?? null, from: l.dragged_defender_start, to: l.dragged_defender_end, link: i };
        legend.add('defender');
      }
      continue; // the runner never has the ball
    }

    if (connectBall && ball && (ball[0] !== start[0] || ball[1] !== start[1])) {
      gaps.push({ from: ball, to: start, before: i });
      legend.add('ball');
    }

    const marker = l.type ? MARKERS[l.type] : undefined;
    if (marker || !end) {
      steps.push({ kind: 'marker', marker: marker ?? 'recovery', link: i, at: start });
      legend.add(marker ?? 'recovery');
      ball = start;
    } else {
      const kind = l.type === 'shot' ? 'shot' : 'pass';
      const cross = l.cross === true;
      steps.push({ kind, link: i, from: start, to: end, cross });
      legend.add(kind === 'shot' ? 'shot' : cross ? 'cross' : 'pass');
      ball = end;
    }
  }
  return { steps, gaps, defender, labels, legend: LEGEND_ORDER.filter((k) => legend.has(k)) };
}

/* ---------- Which play is on the pitch ---------- */

/** Graphics whose play is drawn. Team phase, match keys and the top 3 cite too many events to read. */
const DRAWN = new Set(['goal_analysis', 'card_upgrade', 'mvp_update', 'standout_milestone', 'duel_bar']);
/** At most this many cited events per play, the latest ones. */
export const MAX_EVENTS = 10;

export interface MatchPlay {
  order: OverlayOrder;
  goal: boolean;
  links: PlayLink[];
  /** Space the invisible assist opened, from the goal order. */
  spaceOpened: number | null;
  invisible: string | null;
}

/**
 * The play of the latest graphic up to t that has coordinates. It stays on the pitch until the
 * next one, so it is still there after its graphic leaves the screen.
 */
export function playAt(orders: readonly OverlayOrder[], t: number, events: readonly PlayEvent[], roster: Roster): MatchPlay | null {
  for (let i = orders.length - 1; i >= 0; i--) {
    if (orders[i].show_at_s > t) continue;
    const play = playOf(orders[i], events, roster);
    if (play) return play;
  }
  return null;
}

/** The play behind one graphic, or null when it has nothing to draw. */
export function playOf(o: OverlayOrder, events: readonly PlayEvent[], roster: Roster): MatchPlay | null {
  if (!DRAWN.has(o.type) || o.source_insight === null) return null;
  const byId = new Map(events.map((e) => [e.event_id, e]));

  if (o.type === 'goal_analysis' && hasCoordinates(o.data.chain_detail)) {
    const scorer = o.data.chain[o.data.chain.length - 1];
    const side = roster.player(scorer)?.team.side ?? 'home';
    const ia = o.data.invisible_assist;
    return {
      order: o,
      goal: true,
      links: o.data.chain_detail.map((l) => ({ ...l, side })),
      spaceOpened: typeof ia === 'object' && ia ? ia.space_opened_m : null,
      invisible: invisibleAssistPlayer(ia),
    };
  }

  const cited = (o.evidence ?? [])
    .map((id) => byId.get(id))
    .filter((e): e is PlayEvent => !!e && e.type !== 'goal')
    .sort((a, b) => a.t_s - b.t_s)
    .slice(-MAX_EVENTS);
  if (!cited.length) return null;
  return {
    order: o,
    goal: false,
    links: cited.map((e) => ({
      event_id: e.event_id, player: e.player, action: '', credit: 0, t_s: e.t_s,
      type: e.type as ChainLink['type'], start: e.start, end: e.end, cross: e.cross, lines_broken: e.lines_broken,
      dragged_defender: e.dragged_defender, dragged_defender_start: e.dragged_defender_start, dragged_defender_end: e.dragged_defender_end,
      side: roster.team(e.team)?.side ?? 'home',
    })),
    spaceOpened: cited.find((e) => e.space_opened_m != null)?.space_opened_m ?? null,
    invisible: null,
  };
}
