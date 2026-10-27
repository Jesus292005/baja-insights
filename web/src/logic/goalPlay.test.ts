import { describe, expect, it } from 'vitest';
import type { ChainLink, GoalAnalysisOrder } from '../contracts/overlay';
import { demoMatch } from '../data/match';
import { buildGoalPlay, hasCoordinates, playViewBox, toSvg } from './goalPlay';

const goals = demoMatch.overlays.filter((o): o is GoalAnalysisOrder => o.type === 'goal_analysis' && o.mode === 'fan' && o.language === 'en');
const equaliser = goals.find((o) => o.data.scoreline?.home === 1)!.data.chain_detail!;

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

describe('buildGoalPlay on the 1-1', () => {
  const play = buildGoalPlay(equaliser);

  it('draws the recovery as a dot, the run, the pass and the shot', () => {
    expect(play.steps.map((s) => s.kind)).toEqual(['dot', 'run', 'pass', 'shot']);
  });

  it('joins the ball from Cota to Salgado, skipping Torres, who never touched it', () => {
    expect(play.gaps).toEqual([{ from: [48, 30], to: [70, 38], before: 2 }]);
  });

  it('moves Cárdenas as the engine says', () => {
    expect(play.defender).toEqual({ name: 'G. Cárdenas', from: [90, 37], to: [92, 27.7], link: 1 });
  });

  it('labels each player at the start of their action', () => {
    expect(play.labels.map((l) => l.player)).toEqual(['F. Cota', 'J. Torres', 'R. Salgado', 'M. Ramírez']);
  });
});

describe('buildGoalPlay on the 0-1', () => {
  it('needs no gap when each pass starts where the last one ended, and marks the cross', () => {
    const opener = goals.find((o) => o.data.scoreline?.away === 1 && o.data.scoreline.home === 0)!.data.chain_detail!;
    const play = buildGoalPlay(opener);
    expect(play.steps.map((s) => s.kind)).toEqual(['dot', 'pass', 'pass', 'shot']);
    expect(play.steps.some((s) => s.kind === 'pass' && s.cross)).toBe(true);
    expect(play.gaps).toHaveLength(1);
    expect(play.defender).toBeNull();
  });
});

describe('playViewBox', () => {
  it('zooms in on the 1-1, keeps a 3:2 aspect and covers every point', () => {
    const play = buildGoalPlay(equaliser);
    const [x, y, w, h] = playViewBox(play);
    expect(w / h).toBeCloseTo(1.5);
    expect(w).toBeLessThan(1050 * 0.7);
    for (const p of [[48, 30], [78, 10], [92, 26], [70, 38], [93, 42], [105, 35], [90, 37]] as const) {
      const [sx, sy] = toSvg(p as [number, number]);
      expect(sx).toBeGreaterThanOrEqual(x);
      expect(sx).toBeLessThanOrEqual(x + w);
      expect(sy).toBeGreaterThanOrEqual(y);
      expect(sy).toBeLessThanOrEqual(y + h);
    }
  });

  it('falls back to the whole pitch with nothing to draw', () => {
    expect(playViewBox({ steps: [], gaps: [], defender: null, labels: [] })).toEqual([0, 0, 1050, 680]);
  });
});
