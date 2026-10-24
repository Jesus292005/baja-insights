import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { OverlayOrder } from '../contracts/overlay';
import { demoMatch } from '../data/match';
import { ReplaySource } from './replaySource';
import { createMatchStore } from './store';
import { MAX_ATTEMPTS, WebSocketSource } from './wsSource';

describe('store', () => {
  it('deduplicates orders and keeps them sorted', () => {
    const store = createMatchStore();
    const [a, b] = demoMatch.overlays.slice(0, 2);
    store.orders([b, a]);
    store.orders([a]);
    expect(store.getSnapshot().orders.map((o) => o.overlay_id)).toEqual([a, b].sort((x, y) => x.show_at_s - y.show_at_s || x.overlay_id.localeCompare(y.overlay_id)).map((o) => o.overlay_id));
  });
});

describe('ReplaySource', () => {
  let now = 0;
  beforeEach(() => {
    vi.useFakeTimers();
    now = 0;
  });
  afterEach(() => vi.useRealTimers());

  const make = (opts: Partial<ConstructorParameters<typeof ReplaySource>[0]> = {}) =>
    new ReplaySource({ orders: demoMatch.overlays, events: demoMatch.events, now: () => now, autoplay: true, ...opts });

  it('reports the scoreline from the events, not from the orders', () => {
    const r = make();
    expect(r.stateAt(0).scoreline).toEqual({ home: 0, away: 0 });
    const goal = demoMatch.events.find((e) => e.type === 'goal')!;
    expect(r.stateAt(goal.t_s).scoreline).toEqual(goal.scoreline);
    expect(r.stateAt(5400).scoreline).toEqual(demoMatch.events.find((e) => e.type === 'match_end')!.scoreline);
  });

  it('sends orders a little before show_at_s and advances the clock', () => {
    const store = createMatchStore();
    const r = make({ speed: 10, skip: false });
    r.start(store);
    now = 1000;
    r.tick();
    const snap = store.getSnapshot();
    expect(snap.clock?.t).toBeCloseTo(10);
    expect(snap.orders.every((o: OverlayOrder) => o.show_at_s <= 12)).toBe(true);
    expect(snap.connection.status).toBe('replay');
    r.stop();
  });

  it('in skip mode stops at the next graphic and then runs in real time', () => {
    const store = createMatchStore();
    const r = make({ speed: 60, skip: true });
    const first = 100;
    r.setPacing({ busy: (t) => t >= first && t < first + 5, nextStart: (t) => (t < first ? first : null) });
    r.start(store);
    now = 5000;
    r.tick();
    expect(r.getState().t).toBe(first);
    now = 6000;
    r.tick();
    expect(r.getState().t).toBeCloseTo(first + 1);
    r.stop();
  });

  it('seeks and pauses at the end', () => {
    const store = createMatchStore();
    const r = make({ speed: 60, skip: false });
    r.start(store);
    r.seek(r.getState().end - 1);
    now = 1000;
    r.tick();
    expect(r.getState().playing).toBe(false);
    expect(store.getSnapshot().clock?.phase).toBe('full_time');
    r.stop();
  });
});

class FakeSocket {
  static all: FakeSocket[] = [];
  sent: string[] = [];
  readyState = 0;
  onopen: ((ev: Event) => unknown) | null = null;
  onmessage: ((ev: MessageEvent) => unknown) | null = null;
  onclose: ((ev: CloseEvent) => unknown) | null = null;
  onerror: ((ev: Event) => unknown) | null = null;
  constructor(public url: string) {
    FakeSocket.all.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
  }
  open() {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }
  message(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) } as MessageEvent);
  }
  drop() {
    this.onclose?.({} as CloseEvent);
  }
}

describe('WebSocketSource', () => {
  let now = 0;
  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.all = [];
    now = 0;
  });
  afterEach(() => vi.useRealTimers());

  const make = () =>
    new WebSocketSource({ url: 'wss://x', matchId: 'm001', now: () => now, createSocket: (u) => new FakeSocket(u) as unknown as WebSocket });

  it('subscribes, goes live on the first clock and passes orders and state through', () => {
    const store = createMatchStore();
    const ws = make();
    ws.start(store);
    const s = FakeSocket.all[0];
    s.open();
    expect(JSON.parse(s.sent[0])).toEqual({ kind: 'subscribe', match_id: 'm001', from_t_s: 0 });
    s.message({ kind: 'clock', match_id: 'm001', t_s: 60, period: 1, phase: 'live' });
    s.message({ kind: 'state', match_id: 'm001', t_s: 60, home: 'Bahía FC', away: 'Real Cardón', scoreline: { home: 0, away: 0 } });
    s.message({ kind: 'overlay', order: demoMatch.overlays[0] });
    s.message({ kind: 'clock', match_id: 'other', t_s: 999, period: 2, phase: 'live' });
    const snap = store.getSnapshot();
    expect(snap.connection.status).toBe('live');
    expect(snap.clock?.t).toBe(60);
    expect(snap.state?.scoreline).toEqual({ home: 0, away: 0 });
    expect(snap.orders).toHaveLength(1);
    ws.stop();
  });

  it('reconnects when the heartbeat stops and resubscribes from the last second', () => {
    const store = createMatchStore();
    const ws = make();
    ws.start(store);
    FakeSocket.all[0].open();
    FakeSocket.all[0].message({ kind: 'clock', match_id: 'm001', t_s: 120, period: 1, phase: 'live' });
    now = 3500;
    ws.tick();
    expect(store.getSnapshot().connection.status).toBe('reconnecting');
    expect(store.getSnapshot().lastDataS).toBe(120);
    vi.advanceTimersByTime(1000);
    const second = FakeSocket.all[1];
    second.open();
    expect(JSON.parse(second.sent[0]).from_t_s).toBe(120);
    ws.stop();
  });

  it('goes offline after the last attempt and recovers with retry()', () => {
    const store = createMatchStore();
    const ws = make();
    ws.start(store);
    for (let i = 0; i < MAX_ATTEMPTS + 1; i++) {
      FakeSocket.all[FakeSocket.all.length - 1].drop();
      vi.advanceTimersByTime(10_000);
    }
    expect(store.getSnapshot().connection.status).toBe('offline');
    const before = FakeSocket.all.length;
    ws.retry();
    expect(FakeSocket.all.length).toBe(before + 1);
    expect(store.getSnapshot().connection.status).toBe('reconnecting');
    ws.stop();
  });

  it('marks the end of the stream', () => {
    const store = createMatchStore();
    const ws = make();
    ws.start(store);
    FakeSocket.all[0].open();
    FakeSocket.all[0].message({ kind: 'error', code: 'stream_ended' });
    expect(store.getSnapshot().connection).toEqual({ status: 'offline', code: 'stream_ended' });
    ws.stop();
  });
});
