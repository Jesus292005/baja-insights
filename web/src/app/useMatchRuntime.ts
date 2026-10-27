import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import type { Language, Mode, OverlayOrder } from '../contracts/overlay';
import { demoMatch } from '../data/match';
import { forViewer } from '../logic/derive';
import { isBusy, nextStart, planStage, stageAt } from '../logic/plan';
import { ReplaySource, type ReplayState } from '../stream/replaySource';
import { createMatchStore } from '../stream/store';
import type { MatchSource } from '../stream/types';
import { WebSocketSource } from '../stream/wsSource';
import type { AppConfig } from './config';

const noSubscribe = () => () => {};
const noReplay = () => null;

/** Creates the source once, feeds the store and derives what the viewer sees at the current clock. */
export function useMatchRuntime(config: AppConfig, mode: Mode, lang: Language) {
  const [runtime] = useState(() => {
    const store = createMatchStore();
    const replay =
      config.source === 'replay'
        ? new ReplaySource({
            orders: demoMatch.overlays,
            events: demoMatch.events,
            speed: config.speed,
            skip: config.skip,
            autoplay: config.autoplay,
            startAt: config.startAt,
          })
        : null;
    const source: MatchSource = replay ?? new WebSocketSource({ url: config.streamUrl!, matchId: demoMatch.matchId });
    return { store, source, replay };
  });

  useEffect(() => {
    runtime.source.start(runtime.store);
    return () => runtime.source.stop();
  }, [runtime]);

  const snap = useSyncExternalStore(runtime.store.subscribe, runtime.store.getSnapshot);
  const replayState: ReplayState | null = useSyncExternalStore(
    runtime.replay?.subscribe ?? noSubscribe,
    runtime.replay?.getState ?? noReplay,
  );

  const orders = useMemo(() => forViewer(snap.orders, mode, lang), [snap.orders, mode, lang]);
  const plan = useMemo(() => planStage(orders), [orders]);

  useEffect(() => {
    runtime.replay?.setPacing({ busy: (t) => isBusy(plan, t), nextStart: (t) => nextStart(plan, t) });
  }, [runtime, plan]);

  const t = snap.clock?.t ?? 0;
  const status = snap.connection.status;
  return {
    snap,
    orders,
    t,
    showing: stageAt(plan, t),
    loading: snap.clock === null,
    stale: status === 'reconnecting' || status === 'offline',
    replay: runtime.replay,
    replayState,
    retry: () => runtime.source.retry(),
    /** Adds orders made in this browser, such as a chat answer put on screen. Same dedup as the stream. */
    inject: (orders: OverlayOrder[]) => runtime.store.orders(orders),
  };
}
