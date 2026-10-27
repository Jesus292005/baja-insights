import type { OverlayOrder } from '../contracts/overlay';
import type { StructuralEvent } from '../data/match';
import type { MatchSource, MatchState, Phase, SourceSink } from './types';

/**
 * Plays a recorded match as if it came from the stream service: orders, clock and the
 * scoreline from the match's own events. Lets the UI run with no server.
 *
 * "Skip" mode fast-forwards only while the stage is empty and drops to real time while a
 * graphic is on screen, so every graphic stays up for its real duration_s.
 */

export interface Pacing {
  busy(t: number): boolean;
  nextStart(t: number): number | null;
}

/** Pace of a dead ball in skip mode, at least (match seconds per second). */
export const DEAD_SPEED = 8;
/** The fast-forward stops this long before the restart, so the restart is seen. */
const DEAD_LEAD_S = 1.5;
/** Shorter stoppages are not worth speeding up. */
const DEAD_MIN_S = 3;

export interface ReplayState {
  playing: boolean;
  speed: number;
  skip: boolean;
  t: number;
  end: number;
}

export interface ReplayOptions {
  orders: OverlayOrder[];
  events: StructuralEvent[];
  speed?: number;
  skip?: boolean;
  autoplay?: boolean;
  startAt?: number;
  /** Seconds before show_at_s that an order is "received", like a real stream. */
  leadS?: number;
  tickMs?: number;
  now?: () => number;
}

const NO_PACING: Pacing = { busy: () => false, nextStart: () => null };

export class ReplaySource implements MatchSource {
  private sink: SourceSink | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private pacing: Pacing = NO_PACING;
  /** Dead-ball spells (ball out until the restart), sorted. See setDeadBall. */
  private dead: { from: number; to: number }[] = [];
  private readonly orders: OverlayOrder[];
  private readonly events: StructuralEvent[];
  private readonly lead: number;
  private readonly tickMs: number;
  private readonly now: () => number;
  private sent = 0;
  private last = 0;
  private lastStateKey = '';
  private listeners = new Set<() => void>();
  private state: ReplayState;

  constructor(opts: ReplayOptions) {
    this.orders = [...opts.orders].sort((a, b) => a.show_at_s - b.show_at_s);
    this.events = [...opts.events].sort((a, b) => a.t_s - b.t_s);
    this.lead = opts.leadS ?? 2;
    this.tickMs = opts.tickMs ?? 100;
    this.now = opts.now ?? (() => performance.now());
    const lastOrder = this.orders[this.orders.length - 1];
    const end = Math.max(lastOrder ? lastOrder.show_at_s + lastOrder.duration_s + 2 : 0, this.matchEnd() ?? 5400);
    this.state = {
      playing: opts.autoplay ?? true,
      speed: opts.speed ?? 60,
      skip: opts.skip ?? true,
      t: Math.min(opts.startAt ?? 0, end),
      end,
    };
  }

  /* ---------- MatchSource ---------- */

  start(sink: SourceSink) {
    this.sink = sink;
    sink.connection({ status: 'replay' });
    this.publish(true);
    this.last = this.now();
    this.timer = setInterval(() => this.tick(), this.tickMs);
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.sink = null;
  }

  retry() {
    /* a replay never disconnects */
  }

  /* ---------- Controls ---------- */

  setPacing(pacing: Pacing) {
    this.pacing = pacing;
  }

  /**
   * Dead-ball spells, from the illustrative positions' set_pieces: in skip mode they pass at
   * DEAD_SPEED at least, unless a graphic is on screen, and slow down just before the restart.
   */
  setDeadBall(spells: readonly { from: number; to: number }[]) {
    this.dead = spells.filter((s) => s.to - s.from >= DEAD_MIN_S).sort((a, b) => a.from - b.from);
  }

  /** Where the fast-forward of the dead ball around t stops, or null when the ball is live. */
  private deadUntil(t: number): number | null {
    for (const s of this.dead) {
      if (s.from > t) break;
      if (t < s.to - DEAD_LEAD_S) return s.to - DEAD_LEAD_S;
    }
    return null;
  }

  getState = () => this.state;

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  play() {
    if (this.state.t >= this.state.end) this.seek(0);
    this.last = this.now();
    this.update({ playing: true });
  }

  pause() {
    this.update({ playing: false });
  }

  seek(t: number) {
    this.update({ t: Math.max(0, Math.min(t, this.state.end)) });
    this.publish(true);
  }

  setSpeed(speed: number) {
    this.update({ speed: Math.max(1, speed) });
  }

  setSkip(skip: boolean) {
    this.update({ skip });
  }

  /* ---------- Internals ---------- */

  /** Advances the clock. Exposed for tests. */
  tick() {
    const now = this.now();
    const dt = (now - this.last) / 1000;
    this.last = now;
    const { playing, speed, skip, end } = this.state;
    if (!playing) return;

    const from = this.state.t;
    let t = from;
    if (skip && speed > 1) {
      if (this.pacing.busy(t)) {
        t += dt;
      } else {
        // Never jump over the moment a graphic starts: stop at the next planned start, or at the
        // next order's show_at_s if the viewer's plan has not received it yet.
        const target = t + dt * speed;
        const stops = [this.pacing.nextStart(t), this.nextOrderAfter(t)].filter((x): x is number => x !== null && x < target);
        t = stops.length ? Math.min(...stops) : target;
      }
    } else {
      t += dt * speed;
    }

    // Dead ball with nothing on screen: pass it quickly, stopping just before the restart and
    // never over the start of a graphic.
    const until = skip && !this.pacing.busy(from) ? this.deadUntil(from) : null;
    if (until !== null) {
      const fast = from + dt * Math.max(speed, DEAD_SPEED);
      const stops = [until, this.pacing.nextStart(from), this.nextOrderAfter(from)].filter((x): x is number => x !== null && x > from);
      t = Math.max(t, Math.min(fast, ...stops));
    }

    if (t >= end) {
      this.update({ t: end, playing: false });
    } else {
      this.update({ t });
    }
    this.publish(false);
  }

  private update(patch: Partial<ReplayState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((l) => l());
  }

  private publish(full: boolean) {
    const sink = this.sink;
    if (!sink) return;
    const { t } = this.state;

    let upTo = this.sent;
    while (upTo < this.orders.length && this.orders[upTo].show_at_s <= t + this.lead) upTo++;
    if (upTo > this.sent || full) {
      sink.orders(this.orders.slice(0, upTo));
      this.sent = Math.max(this.sent, upTo);
    }

    const state = this.stateAt(t);
    const key = `${state.scoreline.home}-${state.scoreline.away}-${state.t_s}`;
    if (full || key !== this.lastStateKey) {
      this.lastStateKey = key;
      sink.state(state);
    }

    sink.clock({ t, period: t < 2700 ? 1 : 2, phase: this.phaseAt(t) });
  }

  private nextOrderAfter(t: number): number | null {
    let lo = 0;
    let hi = this.orders.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.orders[mid].show_at_s <= t) lo = mid + 1;
      else hi = mid;
    }
    return lo < this.orders.length ? this.orders[lo].show_at_s : null;
  }

  private matchEnd() {
    return this.events.find((e) => e.type === 'match_end')?.t_s;
  }

  private phaseAt(t: number): Phase {
    const start = this.events.find((e) => e.type === 'match_start')?.t_s ?? 0;
    const end = this.matchEnd();
    if (t < start) return 'pre';
    if (end !== undefined && t >= end) return 'full_time';
    const half = this.events.find((e) => e.type === 'half_time')?.t_s;
    const second = this.events.find((e) => e.type === 'second_half_start')?.t_s;
    if (half !== undefined && second !== undefined && t >= half && t < second) return 'half_time';
    return 'live';
  }

  /** Scoreline as of t, from the last event that carries one. Never worked out from the orders. */
  stateAt(t: number): MatchState {
    const start = this.events.find((e) => e.type === 'match_start');
    let scoreline = { home: 0, away: 0 };
    let at = start?.t_s ?? 0;
    for (const e of this.events) {
      if (e.t_s > t) break;
      if (e.scoreline) {
        scoreline = e.scoreline;
        at = e.t_s;
      }
    }
    return { home: start?.home ?? '', away: start?.away ?? '', scoreline, t_s: at };
  }
}
