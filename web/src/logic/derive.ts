import type {
  CardAttribute, DuelBarOrder, Language, Mode, MvpUpdateOrder, OverlayOrder, RankingEntry, Top3Order,
} from '../contracts/overlay';
import { appliesTo } from '../contracts/overlay';
import type { PlayerRef, Roster } from '../data/roster';

/**
 * Selectors for the persistent panels. They pick and copy values from the orders;
 * none of them computes a number the engine did not send.
 */

export const forViewer = (orders: readonly OverlayOrder[], mode: Mode, language: Language) =>
  orders.filter((o) => appliesTo(o, mode, language));

const due = (o: OverlayOrder, t: number) => o.show_at_s <= t;

/* ---------- Duel ---------- */

export interface DuelView {
  playerA: string;
  playerB: string;
  /** Engine value −1..1 from the latest notice or frame. */
  bar: number;
  asOfS: number;
  /** Latest notice (with text) for this pair, if any. */
  notice: DuelBarOrder | null;
}

export function duelAt(orders: readonly OverlayOrder[], t: number): DuelView | null {
  let latest: DuelBarOrder | null = null;
  let notice: DuelBarOrder | null = null;
  for (const o of orders) {
    if (o.type !== 'duel_bar' || !due(o, t)) continue;
    latest = o;
    if (o.source_insight !== null) notice = o;
  }
  if (!latest) return null;
  const samePair = notice && notice.data.player_a === latest.data.player_a && notice.data.player_b === latest.data.player_b;
  return {
    playerA: latest.data.player_a,
    playerB: latest.data.player_b,
    bar: latest.data.bar,
    asOfS: latest.show_at_s,
    notice: samePair ? notice : null,
  };
}

/* ---------- MVP ---------- */

export interface MvpView {
  /** Full ranking, only when an order carries it (data.ranking, contract v1.1) or from the final top 3. */
  ranking: RankingEntry[] | Top3Order['data']['cards'] | null;
  rankingAsOfS: number | null;
  rankingIsFinal: boolean;
  /** Rank changes, newest first. */
  moves: MvpUpdateOrder[];
}

export function mvpAt(orders: readonly OverlayOrder[], t: number, maxMoves = 5): MvpView {
  const moves: MvpUpdateOrder[] = [];
  let ranking: MvpView['ranking'] = null;
  let rankingAsOfS: number | null = null;
  let rankingIsFinal = false;
  for (const o of orders) {
    if (!due(o, t)) continue;
    if (o.type === 'mvp_update') {
      moves.push(o);
      if (o.data.ranking?.length) {
        ranking = o.data.ranking;
        rankingAsOfS = o.show_at_s;
        rankingIsFinal = false;
      }
    } else if (o.type === 'top3' && o.data.cards.length) {
      ranking = o.data.cards;
      rankingAsOfS = o.show_at_s;
      rankingIsFinal = true;
    }
  }
  return { ranking, rankingAsOfS, rankingIsFinal, moves: moves.reverse().slice(0, maxMoves) };
}

/* ---------- Cards ---------- */

export interface CardChange {
  attribute: CardAttribute;
  from: number;
  to: number;
  delta: number;
  atS: number;
  reason?: string;
  /** Title of the order that carried the change, as context for the analyst view. */
  title: string | null;
}

export interface CardView {
  player: PlayerRef;
  attributes: Record<CardAttribute, number>;
  /** Engine's overall. null when there are changes but the order did not carry overall_to. */
  overall: number | null;
  changes: CardChange[];
}

/** Starting card from teams.json, with each attribute replaced by the last `to` the engine sent. */
export function cardAt(roster: Roster, orders: readonly OverlayOrder[], name: string, t: number): CardView | null {
  const player = roster.player(name);
  if (!player) return null;
  const attributes = { ...player.card };
  const changes: CardChange[] = [];
  const seen = new Set<string>();
  let overall: number | null = player.overall;
  for (const o of orders) {
    const c = o.card;
    if (!c || c.player !== player.name || !due(o, t)) continue;
    const key = `${o.source_insight ?? o.overlay_id}:${c.attribute}`;
    if (seen.has(key)) continue;
    seen.add(key);
    attributes[c.attribute] = c.to;
    overall = c.overall_to ?? null;
    changes.push({ attribute: c.attribute, from: c.from, to: c.to, delta: c.delta, atS: o.show_at_s, reason: c.reason, title: o.title });
  }
  return { player, attributes, overall, changes };
}

/** Players whose card changed up to t, most recent first. */
export function playersWithChanges(orders: readonly OverlayOrder[], t: number): string[] {
  const out: string[] = [];
  for (let i = orders.length - 1; i >= 0; i--) {
    const o = orders[i];
    if (o.card && due(o, t) && !out.includes(o.card.player)) out.push(o.card.player);
  }
  return out;
}

/* ---------- Moments ---------- */

/** Duel-bar animation frames: no text, only move the bar. */
export const isFrame = (o: OverlayOrder) => o.type === 'duel_bar' && o.source_insight === null;

/** Orders already shown, newest first. Duel frames are left out; chat answers (no insight) stay in. */
export const momentsAt = (orders: readonly OverlayOrder[], t: number, limit = 40) =>
  orders.filter((o) => !isFrame(o) && due(o, t)).reverse().slice(0, limit);
