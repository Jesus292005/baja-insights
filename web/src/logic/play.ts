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
/** The pitch backdrop's viewBox: the pitch plus a margin, wider on the sides for the goal names. */
export const VIEW_BOX = { x: -70, y: -30, w: 1190, h: 740 } as const;

/**
 * Halves. The engine keeps one frame for the whole match (Bahía FC always attacks x = 105,
 * docs/aviso-cadena-coordenadas.md), but on screen the teams swap ends at half time: the second
 * half is drawn turned 180°, as a fixed camera would see it.
 */
export type Half = 1 | 2;
/** Second-half kick-off: half_time comes at second 2700 (docs/estado-motor-v1.1.md). */
export const SECOND_HALF_S = 2700;
export const halfOf = (t_s: number): Half => (t_s >= SECOND_HALF_S ? 2 : 1);
/** Engine point to the point drawn in that half. */
export const inHalf = (p: PitchPoint, half: Half): PitchPoint => (half === 2 ? [105 - p[0], 68 - p[1]] : p);
/**
 * The same play drawn in another half. The engine frame is the same in both halves, so turning a
 * play keeps it right against the goals on screen: used to draw the latest play in the half the
 * clock is in, so the ends swap right at 45:00 whatever play is on the pitch.
 */
export const drawnIn = <P extends { half: Half }>(play: P | null, half: Half): P | null => (play ? { ...play, half } : null);
/** Side of the pitch (left or right on screen) whose goal a team defends in a half. */
export const defendsLeft = (side: Side, half: Half) => (side === 'home') === (half === 1);
/** Pitch metres (origin bottom-left) to the 1050 × 680 SVG (y grows downwards). */
export const toSvg = ([x, y]: PitchPoint): [number, number] => [x * 10, (68 - y) * 10];
/** Control point of a cross (SVG units): the ball bends towards the middle of the pitch. */
export const crossControl = ([x1, y1]: [number, number], [x2, y2]: [number, number]): [number, number] => [
  (x1 + x2) / 2 + (y2 - y1) * 0.25,
  (y1 + y2) / 2 + (PITCH_H / 2 - (y1 + y2) / 2) * 0.35,
];

export type Side = 'home' | 'away';
export type MarkerKind = 'recovery' | 'duel' | 'pressure';
export type LegendKind = 'pass' | 'cross' | 'shot' | 'ball' | 'run' | 'defender' | MarkerKind;

/** A link of a play, with the side of the team that made it (for its colour). */
export interface PlayLink extends ChainLink {
  side: Side;
  /** Possession the action belongs to. Goal chains leave it out: the whole chain is one possession. */
  group?: number | null;
}

export type PlayStep =
  | { kind: 'marker'; marker: MarkerKind; link: number; at: PitchPoint }
  | { kind: 'pass' | 'shot' | 'run'; link: number; from: PitchPoint; to: PitchPoint; cross: boolean };

export interface DrawnPlay {
  steps: PlayStep[];
  gaps: { from: PitchPoint; to: PitchPoint; before: number }[];
  defender: { name: string | null; from: PitchPoint; to: PitchPoint; link: number } | null;
  labels: { link: number; player: string; at: PitchPoint }[];
  /**
   * Minute tags, one per possession, when the actions come from several possessions: those are
   * separate actions of the match, not one play, so they are not joined by the ball.
   */
  tags: { link: number; at: PitchPoint; t_s: number }[];
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

/** Possession of a link, when it says one (see PlayLink.group). */
const groupOf = (l: ChainLink) => (l as Partial<PlayLink>).group ?? null;

export function buildPlay(links: readonly ChainLink[], connectBall: boolean): DrawnPlay {
  const ordered = links.map((l, i) => ({ l, i })).sort((a, b) => a.l.t_s - b.l.t_s || a.i - b.i);
  const steps: PlayStep[] = [];
  const gaps: DrawnPlay['gaps'] = [];
  const labels: DrawnPlay['labels'] = [];
  const tags: DrawnPlay['tags'] = [];
  const legend = new Set<LegendKind>();
  let defender: DrawnPlay['defender'] = null;
  let ball: PitchPoint | null = null;
  const groups = new Set(ordered.filter(({ l }) => isPoint(l.start)).map(({ l }) => groupOf(l)));
  const separate = groups.size > 1;
  let group: number | null | undefined;

  for (const { l, i } of ordered) {
    if (!isPoint(l.start)) continue;
    const start = l.start;
    // A new possession starts a new action: the ball of the last one does not carry over.
    if (groupOf(l) !== group) {
      group = groupOf(l);
      ball = null;
      if (separate) tags.push({ link: i, at: start, t_s: l.t_s });
    }
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
  return { steps, gaps, defender, labels, tags, legend: LEGEND_ORDER.filter((k) => legend.has(k)) };
}

/* ---------- Which play is on the pitch ---------- */

/** Graphics whose play is drawn. Team phase, match keys and the top 3 cite too many events to read. */
const DRAWN = new Set(['goal_analysis', 'card_upgrade', 'mvp_update', 'standout_milestone', 'duel_bar']);
/** At most this many cited events per play, the latest ones. */
export const MAX_EVENTS = 10;

export interface MatchPlay {
  order: OverlayOrder;
  goal: boolean;
  /** Half the play is drawn in: that of its latest action (see orientPlay). */
  half: Half;
  links: PlayLink[];
  /** Space the invisible assist opened, from the goal order. */
  spaceOpened: number | null;
  invisible: string | null;
}

/** Half of a play: that of its latest action, so a card citing both halves follows the latest one. */
const playHalf = (links: readonly { t_s: number }[]): Half => halfOf(Math.max(...links.map((l) => l.t_s)));

const flip = (p: PitchPoint | null | undefined, half: Half) => (Array.isArray(p) ? inHalf(p, half) : p);

/** The links of a play as drawn in its half: in the second half every point is turned 180°. */
export function orientPlay(play: MatchPlay): PlayLink[] {
  if (play.half === 1) return play.links;
  return play.links.map((l) => ({
    ...l,
    start: flip(l.start, 2) as PitchPoint,
    end: flip(l.end, 2),
    dragged_defender_start: flip(l.dragged_defender_start, 2),
    dragged_defender_end: flip(l.dragged_defender_end, 2),
  }));
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

/**
 * The play of the graphics on screen now: the newest one that has something to draw. The pitch
 * clears when its card leaves, so no symbol or minute of an old play stays behind.
 */
export function playOnScreen(on: readonly { order: OverlayOrder }[], events: readonly PlayEvent[], roster: Roster): MatchPlay | null {
  const newest = [...on].sort((a, b) => b.order.show_at_s - a.order.show_at_s);
  for (const { order } of newest) {
    const play = playOf(order, events, roster);
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
      half: playHalf(o.data.chain_detail),
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
    half: playHalf(cited),
    links: cited.map((e) => ({
      event_id: e.event_id, player: e.player, action: '', credit: 0, t_s: e.t_s,
      type: e.type as ChainLink['type'], start: e.start, end: e.end, cross: e.cross, lines_broken: e.lines_broken,
      dragged_defender: e.dragged_defender, dragged_defender_start: e.dragged_defender_start, dragged_defender_end: e.dragged_defender_end,
      side: roster.team(e.team)?.side ?? 'home',
      // Without a possession, each event stands alone.
      group: e.possession_id ?? -e.event_id,
    })),
    spaceOpened: cited.find((e) => e.space_opened_m != null)?.space_opened_m ?? null,
    invisible: null,
  };
}
