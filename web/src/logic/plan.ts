import type { OverlayOrder, Slot } from '../contracts/overlay';

/**
 * Decides, second by second, which order each slot shows. Pure function of the viewer's orders.
 *
 * Rules (same spirit as the agents' Scheduler in agents/baja_agents/overlays.py):
 * - One order per slot. The next one waits in a queue, in show_at_s order.
 * - full_screen hides and pauses every other slot. center hides and pauses side_panel and
 *   lower_third, which overlap it. A paused order keeps its remaining time.
 * - An order that waited more than MAX_WAIT_S is dropped, except goals, match keys, the top 3 and
 *   chat answers (someone asked for those to be on screen).
 *   Duel-bar frames (source_insight null) are dropped as soon as they would start late.
 */

export const SLOTS: Slot[] = ['full_screen', 'center', 'top_right', 'side_panel', 'lower_third', 'bottom_bar'];
const BLOCKED_BY_CENTER: Slot[] = ['side_panel', 'lower_third'];
const NEVER_DROP = new Set(['goal_analysis', 'match_keys', 'top3', 'chat_answer']);
export const MAX_WAIT_S = 20;

export interface Showing {
  order: OverlayOrder;
  /** Seconds already on screen at the start of this second. */
  elapsed: number;
}

export type StageFrame = Readonly<Partial<Record<Slot, Showing>>>;

export interface StagePlan {
  /** frames[s] = what is on screen during match second s. */
  frames: StageFrame[];
  /** Seconds at which some order appears, ascending. */
  starts: number[];
  /** overlay_id of orders that never made it on screen. */
  dropped: string[];
}

const EMPTY: StageFrame = Object.freeze({});

export function planStage(orders: readonly OverlayOrder[]): StagePlan {
  const sorted = [...orders].sort((a, b) => a.show_at_s - b.show_at_s || a.overlay_id.localeCompare(b.overlay_id));
  const lastShow = sorted.length ? sorted[sorted.length - 1].show_at_s : 0;
  const horizon = lastShow + 60 + MAX_WAIT_S * 2;

  const queues: Record<Slot, OverlayOrder[]> = { full_screen: [], center: [], top_right: [], side_panel: [], lower_third: [], bottom_bar: [] };
  const current: Partial<Record<Slot, { order: OverlayOrder; elapsed: number; duration: number }>> = {};
  const frames: StageFrame[] = new Array(horizon + 1);
  const starts: number[] = [];
  const dropped: string[] = [];
  let next = 0;

  for (let s = 0; s <= horizon; s++) {
    while (next < sorted.length && sorted[next].show_at_s <= s) {
      queues[sorted[next].slot].push(sorted[next]);
      next++;
    }

    const blocked = (slot: Slot) =>
      (slot !== 'full_screen' && current.full_screen !== undefined) ||
      (BLOCKED_BY_CENTER.includes(slot) && current.center !== undefined);

    let started = false;
    for (const slot of SLOTS) {
      if (current[slot] || blocked(slot)) continue;
      const queue = queues[slot];
      while (queue.length) {
        const order = queue.shift()!;
        const wait = s - order.show_at_s;
        const isFrame = order.type === 'duel_bar' && order.source_insight === null;
        if ((isFrame && wait > 1) || (!NEVER_DROP.has(order.type) && wait > MAX_WAIT_S)) {
          dropped.push(order.overlay_id);
          continue;
        }
        current[slot] = { order, elapsed: 0, duration: Math.max(1, Math.ceil(order.duration_s)) };
        started = true;
        break;
      }
    }
    if (started) starts.push(s);

    // Freeze who is visible this second before anything ends, so a blocker that ends now
    // does not let the paused slots advance in the same second.
    const visible = SLOTS.filter((slot) => current[slot] && !blocked(slot));

    let frame: Partial<Record<Slot, Showing>> | null = null;
    for (const slot of visible) {
      const c = current[slot]!;
      (frame ??= {})[slot] = { order: c.order, elapsed: c.elapsed };
    }
    frames[s] = frame ?? EMPTY;

    for (const slot of visible) {
      const c = current[slot]!;
      c.elapsed += 1;
      if (c.elapsed >= c.duration) delete current[slot];
    }
  }

  return { frames, starts, dropped };
}

/** What is on screen at a fractional match second, with smooth elapsed time. */
export function stageAt(plan: StagePlan, t: number): Partial<Record<Slot, Showing>> {
  const s = Math.floor(t);
  const frame = plan.frames[s];
  if (!frame) return {};
  const frac = t - s;
  const out: Partial<Record<Slot, Showing>> = {};
  for (const slot of SLOTS) {
    const f = frame[slot];
    if (f) out[slot] = { order: f.order, elapsed: Math.min(f.elapsed + frac, f.order.duration_s) };
  }
  return out;
}

export const isBusy = (plan: StagePlan, t: number) => {
  const frame = plan.frames[Math.floor(t)];
  return !!frame && frame !== EMPTY && Object.keys(frame).length > 0;
};

/** First second strictly after t at which an order appears, or null. */
export function nextStart(plan: StagePlan, t: number): number | null {
  const { starts } = plan;
  let lo = 0;
  let hi = starts.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (starts[mid] <= t) lo = mid + 1;
    else hi = mid;
  }
  return lo < starts.length ? starts[lo] : null;
}
