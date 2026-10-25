import type { ConnectionStatus, OverlayOrder, Scoreline } from '../contracts/overlay';

export type Phase = 'pre' | 'live' | 'half_time' | 'full_time';

export interface ClockUpdate {
  /** Match seconds. Fractional on the client so graphics move smoothly; the wire carries integers. */
  t: number;
  period: 1 | 2;
  phase: Phase;
}

export interface MatchState {
  home: string;
  away: string;
  scoreline: Scoreline;
  /** Match second the scoreline belongs to. */
  t_s: number;
}

export interface ConnectionInfo {
  status: ConnectionStatus;
  attempt?: number;
  retryInS?: number;
  /** Error code from the server, e.g. stream_ended. */
  code?: string;
}

/** What any source (replay or WebSocket) reports to the store. */
export interface SourceSink {
  orders(orders: OverlayOrder[]): void;
  clock(update: ClockUpdate): void;
  state(state: MatchState): void;
  connection(info: ConnectionInfo): void;
}

export interface MatchSource {
  start(sink: SourceSink): void;
  stop(): void;
  /** Manual retry after going offline. */
  retry(): void;
}
