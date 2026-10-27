import { describe, expect, it } from 'vitest';
import type { ChainLink, GoalAnalysisOrder, OverlayOrder } from '../contracts/overlay';
import { demoMatch, roster } from '../data/match';
import { forViewer } from './derive';
import { buildPlay, defendsLeft, drawnIn, halfOf, hasCoordinates, orientPlay, playAt, playOnScreen, toSvg } from './play';

const fanEn = forViewer(demoMatch.overlays, 'fan', 'en');
const goals = fanEn.filter((o): o is GoalAnalysisOrder => o.type === 'goal_analysis');
const equaliser = goals.find((o) => o.data.scoreline?.home === 1)!;
const opener = goals.find((o) => o.data.scoreline?.home === 0)!;

describe('toSvg', () => {
  it('flips y, because the pitch origin is bottom-left and SVG grows downwards', () => {
    expect(toSvg([0, 0])).toEqual([0, 680]);
    expect(toSvg([105, 68])).toEqual([1050, 0]);
    expect(toSvg([78, 10])).toEqual([780, 580]);
  });
});

describe('hasCoordinates', () => {
  it('is true for the demo goals and false for v1 links', () => {
    expect(goals.every((o) => hasCoordinates(o.data.chain_detail))).toBe(true);
    const v1: ChainLink = { event_id: 1, player: 'X', action: 'remate', credit: 1, t_s: 1 };
    expect(hasCoordinates([v1])).toBe(false);
    expect(hasCoordinates(undefined)).toBe(false);
  });
});

describe('buildPlay on the 1-1', () => {
  const play = buildPlay(equaliser.data.chain_detail!, true);

  it('draws the recovery as a marker, the run, the pass and the shot', () => {
    expect(play.steps.map((s) => (s.kind === 'marker' ? s.marker : s.kind))).toEqual(['recovery', 'run', 'pass', 'shot']);
  });

  it('joins the ball from Cota to Salgado, skipping Torres, who never touched it', () => {
    expect(play.gaps).toEqual([{ from: [48, 30], to: [70, 38], before: 2 }]);
  });

  it('moves Cárdenas as the engine says', () => {
    expect(play.defender).toEqual({ name: 'G. Cárdenas', from: [90, 37], to: [92, 27.7], link: 1 });
  });

  it('lists in the legend only what is drawn', () => {
    expect(play.legend).toEqual(['pass', 'shot', 'ball', 'run', 'defender', 'recovery']);
  });
});

describe('buildPlay on the 0-1', () => {
  it('marks the cross and has no defender', () => {
    const play = buildPlay(opener.data.chain_detail!, true);
    expect(play.legend).toContain('cross');
    expect(play.defender).toBeNull();
  });

  it('never joins the ball when asked not to (plays that are not a chain)', () => {
    expect(buildPlay(opener.data.chain_detail!, false).gaps).toEqual([]);
  });
});

describe('playAt', () => {
  it('is empty before any graphic with a play', () => {
    expect(playAt(fanEn, 0, demoMatch.playEvents, roster)).toBeNull();
  });

  it('draws the goal chain after the 1-1, and keeps it once the graphic is gone', () => {
    const during = playAt(fanEn, equaliser.show_at_s + 1, demoMatch.playEvents, roster)!;
    expect(during.goal).toBe(true);
    expect(during.order.overlay_id).toBe(equaliser.overlay_id);
    expect(during.links.every((l) => l.side === 'home')).toBe(true);
    expect(during.spaceOpened).toBe(9.5);
    const nextDrawn = fanEn.find((o) => o.show_at_s >= equaliser.show_at_s + equaliser.duration_s && ['card_upgrade', 'mvp_update', 'standout_milestone', 'duel_bar'].includes(o.type) && o.source_insight !== null && o.evidence?.length);
    const after = playAt(fanEn, (nextDrawn?.show_at_s ?? 5400) - 1, demoMatch.playEvents, roster)!;
    expect(after.order.overlay_id).toBe(equaliser.overlay_id);
  });

  it('draws the cited events of other graphics, coloured by team', () => {
    const recoveries = fanEn.find((o) => o.type === 'card_upgrade' && o.card?.reason_code === 'opp_half_recoveries')!;
    const play = playAt(fanEn, recoveries.show_at_s, demoMatch.playEvents, roster)!;
    expect(play.goal).toBe(false);
    expect(play.links.length).toBe(recoveries.evidence!.length);
    expect(play.links.every((l) => l.type === 'recovery')).toBe(true);
    expect(play.links[0].side).toBe(roster.player(recoveries.card!.player)!.team.side);
    expect(buildPlay(play.links, false).labels).toHaveLength(1);
  });

  it('skips duel frames, team phases and graphics without cited events', () => {
    const frame = fanEn.find((o) => o.type === 'duel_bar' && o.source_insight === null)!;
    const only: OverlayOrder[] = [frame, ...fanEn.filter((o) => o.type === 'team_phase')];
    expect(playAt(only, 5520, demoMatch.playEvents, roster)).toBeNull();
  });
});

describe('plays from several possessions', () => {
  const ev = (event_id: number, t_s: number, type: string, group: number, start: [number, number], end?: [number, number]) =>
    ({ event_id, player: 'B. Haro', action: '', credit: 0, t_s, type, start, end, side: 'away', group }) as never;

  it('joins the actions of one possession with the ball', () => {
    const play = buildPlay([ev(1, 10, 'pass', 7, [50, 45], [28, 58]), ev(2, 19, 'shot', 7, [8, 36], [0, 35])], true);
    expect(play.gaps).toHaveLength(1);
    expect(play.tags).toEqual([]);
  });

  it('keeps separate possessions apart, each with its minute', () => {
    const play = buildPlay([ev(1, 983, 'pass', 43, [84, 23], [53, 9]), ev(2, 1210, 'pass', 49, [58, 3], [40, 12])], true);
    expect(play.gaps).toEqual([]);
    expect(play.tags.map((g) => g.t_s)).toEqual([983, 1210]);
  });
});

describe('halves', () => {
  it('turns second-half plays 180° and keeps first-half ones', () => {
    const second = playAt(fanEn, equaliser.show_at_s, demoMatch.playEvents, roster)!;
    expect(second.half).toBe(2);
    const raw = second.links[0].start!;
    expect(orientPlay(second)[0].start).toEqual([105 - raw[0], 68 - raw[1]]);
    const first = playAt(fanEn, opener.show_at_s, demoMatch.playEvents, roster)!;
    expect(first.half).toBe(1);
    expect(orientPlay(first)).toBe(first.links);
  });

  it('puts each team in front of its own goal', () => {
    expect(defendsLeft('home', 1)).toBe(true);
    expect(defendsLeft('away', 1)).toBe(false);
    expect(defendsLeft('home', 2)).toBe(false);
    expect(halfOf(2699)).toBe(1);
    expect(halfOf(2700)).toBe(2);
  });
});

describe('drawnIn', () => {
  it('draws the latest first-half play in the second half once the clock passes 45:00', () => {
    const first = playAt(fanEn, opener.show_at_s, demoMatch.playEvents, roster)!;
    const later = drawnIn(first, halfOf(2700))!;
    expect(later.half).toBe(2);
    const raw = first.links[0].start!;
    expect(orientPlay(later)[0].start).toEqual([105 - raw[0], 68 - raw[1]]);
    expect(drawnIn(null, 2)).toBeNull();
  });
});

describe('playOnScreen', () => {
  it('draws the play of the card on screen, and nothing once it has left', () => {
    expect(playOnScreen([{ order: equaliser }], demoMatch.playEvents, roster)?.order).toBe(equaliser);
    expect(playOnScreen([], demoMatch.playEvents, roster)).toBeNull();
  });

  it('takes the newest card that has a play', () => {
    const play = playOnScreen([{ order: opener }, { order: equaliser }], demoMatch.playEvents, roster);
    expect(play?.order).toBe(equaliser);
  });
});
