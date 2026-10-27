import { describe, expect, it } from 'vitest';
import type { OverlayOrder } from '../contracts/overlay';
import { demoMatch, roster } from '../data/match';
import { cardAt, duelAt, forViewer, momentsAt, mvpAt, playersWithChanges } from './derive';

const fanEs = forViewer(demoMatch.overlays, 'fan', 'es');

describe('forViewer', () => {
  it('keeps the viewer variant and the shared frames', () => {
    expect(fanEs.every((o) => (o.mode === 'fan' || o.mode === 'all') && (o.language === 'es' || o.language === 'all'))).toBe(true);
    expect(fanEs.some((o) => o.mode === 'all')).toBe(true);
  });
});

describe('duelAt', () => {
  it('is empty before the first duel order', () => {
    const first = fanEs.find((o) => o.type === 'duel_bar')!;
    expect(duelAt(fanEs, first.show_at_s - 1)).toBeNull();
  });

  it('takes the bar from the latest frame and keeps the latest notice text', () => {
    const duels = fanEs.filter((o) => o.type === 'duel_bar');
    const frame = duels.find((o) => o.source_insight === null)!;
    const view = duelAt(fanEs, frame.show_at_s)!;
    expect(view.bar).toBe((frame.data as { bar: number }).bar);
    expect(view.notice?.source_insight).not.toBeNull();
  });
});

describe('mvpAt', () => {
  it('lists moves newest first', () => {
    const view = mvpAt(fanEs, 50 * 60);
    expect(view.moves.length).toBeGreaterThan(0);
    expect(view.moves[0].show_at_s).toBeGreaterThanOrEqual(view.moves[view.moves.length - 1].show_at_s);
  });

  it('has no ranking before the top 3 when the orders are v1 (no data.ranking)', () => {
    const v1 = fanEs.map((o) =>
      o.type === 'mvp_update' ? ({ ...o, data: { rank: o.data.rank, previous_rank: o.data.previous_rank, mvp_score: o.data.mvp_score } } as OverlayOrder) : o,
    );
    const view = mvpAt(v1, 50 * 60);
    expect(view.moves.length).toBeGreaterThan(0);
    expect(view.ranking).toBeNull();
  });

  it('takes the ranking of the latest mvp_update in the demo match (v1.1)', () => {
    const t = 50 * 60;
    const latest = fanEs.filter((o) => o.type === 'mvp_update' && o.show_at_s <= t).pop()!;
    const view = mvpAt(fanEs, t);
    expect(view.ranking).toEqual((latest.data as { ranking: unknown }).ranking);
    expect(view.rankingAsOfS).toBe(latest.show_at_s);
    expect(view.rankingIsFinal).toBe(false);
  });

  it('uses data.ranking when an order carries it', () => {
    const move = fanEs.find((o) => o.type === 'mvp_update')!;
    const ranking = [{ rank: 1, player: 'J. Torres', team: 'Bahía FC', position: 'ED' as const, mvp_score: 6.2 }];
    const withRanking = { ...move, data: { ...(move.data as object), ranking } } as OverlayOrder;
    const view = mvpAt([withRanking], move.show_at_s);
    expect(view.ranking).toEqual(ranking);
    expect(view.rankingIsFinal).toBe(false);
  });

  it('finds who made the latest move in the ranking that came with it', () => {
    const t = 50 * 60;
    const latest = fanEs.filter((o) => o.type === 'mvp_update' && o.show_at_s <= t).pop()!;
    const data = latest.data as { rank: number; previous_rank?: number; ranking: { rank: number; player: string }[] };
    const view = mvpAt(fanEs, t);
    expect(view.mover).toEqual({
      player: data.ranking.find((r) => r.rank === data.rank)!.player,
      from: data.previous_rank ?? null,
      to: data.rank,
    });
  });

  it('has no mover without a ranking or after the final top 3', () => {
    const v1 = fanEs.map((o) =>
      o.type === 'mvp_update' ? ({ ...o, data: { rank: o.data.rank, mvp_score: o.data.mvp_score } } as OverlayOrder) : o,
    );
    expect(mvpAt(v1, 50 * 60).mover).toBeNull();
    expect(mvpAt(fanEs, 5520).mover).toBeNull();
  });

  it('uses the final top 3 as the final ranking', () => {
    const view = mvpAt(fanEs, 5520);
    expect(view.rankingIsFinal).toBe(true);
    expect(view.ranking?.map((c) => c.rank)).toEqual([1, 2, 3]);
  });
});

describe('cardAt', () => {
  it('starts from teams.json', () => {
    const card = cardAt(roster, fanEs, 'J. Torres', 0)!;
    expect(card.attributes.defensa).toBe(roster.player('J. Torres')!.card.defensa);
    expect(card.overall).toBe(roster.player('J. Torres')!.overall);
    expect(card.changes).toEqual([]);
  });

  it('applies the last `to` of each change once and keeps the overall the engine sent', () => {
    const name = playersWithChanges(fanEs, 5520)[0];
    const orders = fanEs.filter((o) => o.card?.player === name);
    const last = orders[orders.length - 1];
    const card = cardAt(roster, fanEs, name, 5520)!;
    expect(card.attributes[last.card!.attribute]).toBe(last.card!.to);
    expect(new Set(card.changes.map((c) => `${c.atS}:${c.attribute}`)).size).toBe(card.changes.length);
    expect(card.overall).toBe(last.card!.overall_to);
  });

  it('gives the previous overall only when the latest change moved it', () => {
    const cards = fanEs.filter((o) => o.card?.overall_from !== undefined && o.card.overall_to !== undefined);
    const moved = cards.find((o) => o.card!.overall_from !== o.card!.overall_to)!;
    const same = cards.find((o) => o.card!.overall_from === o.card!.overall_to)!;
    expect(cardAt(roster, [moved], moved.card!.player, moved.show_at_s)!.overallFrom).toBe(moved.card!.overall_from);
    expect(cardAt(roster, [same], same.card!.player, same.show_at_s)!.overallFrom).toBeNull();
    expect(cardAt(roster, fanEs, 'J. Torres', 0)!.overallFrom).toBeNull();
  });

  it('drops the overall when a v1 order changed the card without overall_to', () => {
    const o = fanEs.find((x) => x.card)!;
    const { overall_from: _f, overall_to: _t, ...v1card } = o.card!;
    const v1 = { ...o, card: v1card } as OverlayOrder;
    expect(cardAt(roster, [v1], o.card!.player, o.show_at_s)!.overall).toBeNull();
  });

  it('keeps the overall the engine sends', () => {
    const o = fanEs.find((x) => x.card)!;
    const withOverall = { ...o, card: { ...o.card!, overall_from: 70, overall_to: 71 } } as OverlayOrder;
    expect(cardAt(roster, [withOverall], o.card!.player, o.show_at_s)!.overall).toBe(71);
  });

  it('returns null for a player that is not in the roster', () => {
    expect(cardAt(roster, fanEs, 'Nadie', 10)).toBeNull();
  });
});

describe('momentsAt', () => {
  it('excludes duel frames and future orders', () => {
    const t = 30 * 60;
    const m = momentsAt(fanEs, t);
    expect(m.every((o) => !(o.type === 'duel_bar' && o.source_insight === null) && o.show_at_s <= t)).toBe(true);
  });

  it('keeps chat answers, which have no source insight', () => {
    const chat = { ...fanEs[0], overlay_id: 'chat-abc', source_insight: null, type: 'chat_answer', show_at_s: 100 } as OverlayOrder;
    expect(momentsAt([chat], 200).map((o) => o.overlay_id)).toEqual(['chat-abc']);
  });
});

describe('momentsAt, whole match', () => {
  it('lists every moment of the match at full time', () => {
    const all = fanEs.filter((o) => !(o.type === 'duel_bar' && o.source_insight === null));
    expect(momentsAt(fanEs, 99999)).toHaveLength(all.length);
  });
});
