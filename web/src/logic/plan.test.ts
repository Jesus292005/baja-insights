import { describe, expect, it } from 'vitest';
import type { OverlayOrder, Slot } from '../contracts/overlay';
import { appliesTo } from '../contracts/overlay';
import { demoMatch } from '../data/match';
import { isBusy, nextStart, planStage, stageAt } from './plan';

let n = 0;
const order = (slot: Slot, show: number, duration: number, extra: Partial<OverlayOrder> = {}): OverlayOrder =>
  ({
    overlay_id: `t${String(++n).padStart(3, '0')}`, match_id: 'm', source_insight: 'i01', period: 1,
    show_at: '00:00', show_at_s: show, duration_s: duration, slot, mode: 'all', language: 'all',
    type: 'team_phase', title: 'x', text: 'y', data: { label: 'control' }, ...extra,
  }) as OverlayOrder;

const at = (plan: ReturnType<typeof planStage>, s: number, slot: Slot) => plan.frames[s][slot]?.order.overlay_id;

describe('planStage', () => {
  it('shows an order from show_at_s for duration_s', () => {
    const a = order('side_panel', 10, 3);
    const plan = planStage([a]);
    expect(at(plan, 9, 'side_panel')).toBeUndefined();
    expect([10, 11, 12].map((s) => at(plan, s, 'side_panel'))).toEqual([a.overlay_id, a.overlay_id, a.overlay_id]);
    expect(at(plan, 13, 'side_panel')).toBeUndefined();
    expect(plan.frames[11].side_panel?.elapsed).toBe(1);
  });

  it('queues a second order in the same slot', () => {
    const a = order('side_panel', 10, 3);
    const b = order('side_panel', 11, 2);
    const plan = planStage([a, b]);
    expect(at(plan, 12, 'side_panel')).toBe(a.overlay_id);
    expect(at(plan, 13, 'side_panel')).toBe(b.overlay_id);
    expect(at(plan, 15, 'side_panel')).toBeUndefined();
  });

  it('pauses side_panel while center is on and resumes it with its remaining time', () => {
    const side = order('side_panel', 10, 4);
    const goal = order('center', 12, 3, { type: 'goal_analysis', data: { chain: ['A'], credit: [1] } });
    const plan = planStage([side, goal]);
    expect(at(plan, 11, 'side_panel')).toBe(side.overlay_id);
    expect(at(plan, 12, 'side_panel')).toBeUndefined();
    expect(at(plan, 12, 'center')).toBe(goal.overlay_id);
    expect(at(plan, 15, 'side_panel')).toBe(side.overlay_id);
    expect(plan.frames[15].side_panel?.elapsed).toBe(2);
    expect(at(plan, 17, 'side_panel')).toBeUndefined();
  });

  it('full_screen hides every other slot', () => {
    const bar = order('top_right', 0, 30, { type: 'mvp_update', data: { rank: 1, mvp_score: 1 } });
    const top = order('full_screen', 5, 5, { type: 'top3', data: { cards: [] } });
    const plan = planStage([bar, top]);
    expect(Object.keys(plan.frames[6])).toEqual(['full_screen']);
    expect(at(plan, 10, 'top_right')).toBe(bar.overlay_id);
  });

  it('drops an order that waited too long, but never a goal', () => {
    const long = order('center', 0, 40, { type: 'goal_analysis', data: { chain: ['A'], credit: [1] } });
    const late = order('side_panel', 1, 5);
    const goal2 = order('center', 2, 5, { type: 'goal_analysis', data: { chain: ['B'], credit: [1] } });
    const plan = planStage([long, late, goal2]);
    expect(plan.dropped).toContain(late.overlay_id);
    expect(at(plan, 40, 'center')).toBe(goal2.overlay_id);
  });

  it('drops a duel-bar frame that would start late', () => {
    const notice = order('bottom_bar', 0, 8, { type: 'duel_bar', data: { player_a: 'A', player_b: 'B', bar: 0 } });
    const frame = order('bottom_bar', 3, 4, { type: 'duel_bar', source_insight: null, data: { player_a: 'A', player_b: 'B', bar: 0.2 } });
    expect(planStage([notice, frame]).dropped).toEqual([frame.overlay_id]);
  });

  it('gives smooth elapsed time, busy flag and next start', () => {
    const a = order('top_right', 10, 4, { type: 'mvp_update', data: { rank: 1, mvp_score: 1 } });
    const plan = planStage([a]);
    expect(stageAt(plan, 11.5).top_right?.elapsed).toBeCloseTo(1.5);
    expect(isBusy(plan, 9.9)).toBe(false);
    expect(isBusy(plan, 10)).toBe(true);
    expect(nextStart(plan, 0)).toBe(10);
    expect(nextStart(plan, 10)).toBeNull();
  });

  it('places every demo order for each viewer without overlaps', () => {
    for (const mode of ['fan', 'analyst'] as const) {
      for (const lang of ['es', 'en'] as const) {
        const mine = demoMatch.overlays.filter((o) => appliesTo(o, mode, lang));
        const plan = planStage(mine);
        const goals = mine.filter((o) => o.type === 'goal_analysis' || o.type === 'top3').map((o) => o.overlay_id);
        goals.forEach((id) => expect(plan.dropped).not.toContain(id));
        // the agents already avoid overlaps, so nothing important should be dropped
        expect(plan.dropped.filter((id) => mine.find((o) => o.overlay_id === id)?.source_insight !== null)).toEqual([]);
      }
    }
  });
});
