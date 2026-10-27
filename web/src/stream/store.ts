import type { OverlayOrder } from '../contracts/overlay';
import type { ClockUpdate, ConnectionInfo, MatchState, SourceSink } from './types';

export interface MatchSnapshot {
  /** Every order received, sorted by show_at_s then overlay_id. Deduplicated by overlay_id. */
  orders: OverlayOrder[];
  clock: ClockUpdate | null;
  state: MatchState | null;
  connection: ConnectionInfo;
  /** Last match second with confirmed data (clock or state). */
  lastDataS: number | null;
}

export interface MatchStore extends SourceSink {
  getSnapshot(): MatchSnapshot;
  subscribe(listener: () => void): () => void;
}

const byTime = (a: OverlayOrder, b: OverlayOrder) =>
  a.show_at_s - b.show_at_s || (a.overlay_id < b.overlay_id ? -1 : a.overlay_id > b.overlay_id ? 1 : 0);

/** Small external store for useSyncExternalStore. Each update produces a new snapshot object. */
export function createMatchStore(): MatchStore {
  let snapshot: MatchSnapshot = {
    orders: [],
    clock: null,
    state: null,
    connection: { status: 'connecting' },
    lastDataS: null,
  };
  const ids = new Set<string>();
  const listeners = new Set<() => void>();
  const emit = (next: MatchSnapshot) => {
    snapshot = next;
    listeners.forEach((l) => l());
  };

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    orders(incoming) {
      const fresh = incoming.filter((o) => !ids.has(o.overlay_id));
      if (!fresh.length) return;
      fresh.forEach((o) => ids.add(o.overlay_id));
      emit({ ...snapshot, orders: [...snapshot.orders, ...fresh].sort(byTime) });
    },
    clock(update) {
      emit({ ...snapshot, clock: update, lastDataS: Math.floor(update.t) });
    },
    state(state) {
      emit({ ...snapshot, state });
    },
    connection(info) {
      const prev = snapshot.connection;
      if (prev.status === info.status && prev.attempt === info.attempt && prev.retryInS === info.retryInS && prev.code === info.code) return;
      emit({ ...snapshot, connection: info });
    },
  };
}
