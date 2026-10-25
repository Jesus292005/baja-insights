import type { OverlayOrder, StreamClientMessage, StreamServerMessage } from '../contracts/overlay';
import { HEARTBEAT_TIMEOUT_MS } from '../contracts/overlay';
import type { MatchSource, SourceSink } from './types';

/**
 * Live source over WebSocket, following contracts/stream.schema.json.
 *
 * - On every (re)connect it sends `subscribe` with the last match second it has, so the
 *   server can replay what was missed.
 * - `clock` is the heartbeat. Without one for HEARTBEAT_TIMEOUT_MS the source reports
 *   "reconnecting" and reconnects with exponential backoff (1, 2, 4, 8 s, max 10 s).
 * - After MAX_ATTEMPTS it goes "offline" and waits for retry().
 * - Between heartbeats the clock advances locally for at most MAX_EXTRAPOLATION_S,
 *   so graphics move smoothly but the clock never runs ahead of the data for long.
 */

export const MAX_ATTEMPTS = 6;
const MAX_EXTRAPOLATION_S = 1.5;
const TICK_MS = 100;

type SocketLike = Pick<WebSocket, 'send' | 'close' | 'readyState'> & {
  onopen: ((ev: Event) => unknown) | null;
  onmessage: ((ev: MessageEvent) => unknown) | null;
  onclose: ((ev: CloseEvent) => unknown) | null;
  onerror: ((ev: Event) => unknown) | null;
};

export interface WsOptions {
  url: string;
  matchId: string;
  createSocket?: (url: string) => SocketLike;
  now?: () => number;
}

export class WebSocketSource implements MatchSource {
  private sink: SourceSink | null = null;
  private socket: SocketLike | null = null;
  private attempt = 0;
  private lastT = 0;
  private lastBeatAt = 0;
  private speed = 1;
  private phase: 'pre' | 'live' | 'half_time' | 'full_time' = 'pre';
  private period: 1 | 2 = 1;
  private live = false;
  private ended = false;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private ticker: ReturnType<typeof setInterval> | null = null;
  private readonly createSocket: (url: string) => SocketLike;
  private readonly now: () => number;

  constructor(private readonly opts: WsOptions) {
    this.createSocket = opts.createSocket ?? ((url) => new WebSocket(url) as SocketLike);
    this.now = opts.now ?? (() => performance.now());
  }

  start(sink: SourceSink) {
    this.sink = sink;
    sink.connection({ status: 'connecting' });
    this.connect();
    this.ticker = setInterval(() => this.tick(), TICK_MS);
  }

  stop() {
    this.sink = null;
    if (this.ticker) clearInterval(this.ticker);
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.ticker = this.retryTimer = null;
    this.dropSocket();
  }

  retry() {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.attempt = 0;
    this.ended = false;
    this.sink?.connection({ status: 'reconnecting', attempt: 0 });
    this.connect();
  }

  private connect() {
    this.dropSocket();
    let socket: SocketLike;
    try {
      socket = this.createSocket(this.opts.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      const hello: StreamClientMessage = { kind: 'subscribe', match_id: this.opts.matchId, from_t_s: Math.floor(this.lastT) };
      socket.send(JSON.stringify(hello));
    };
    socket.onmessage = (ev) => this.handle(ev.data);
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.live = false;
      if (!this.ended) this.scheduleReconnect();
    };
    socket.onerror = () => {
      /* onclose follows */
    };
  }

  private dropSocket() {
    const s = this.socket;
    this.socket = null;
    if (s) {
      s.onopen = s.onmessage = s.onclose = s.onerror = null;
      try {
        s.close();
      } catch {
        /* already closed */
      }
    }
  }

  private scheduleReconnect() {
    if (!this.sink) return;
    this.attempt += 1;
    if (this.attempt > MAX_ATTEMPTS) {
      this.sink.connection({ status: 'offline', attempt: this.attempt - 1 });
      return;
    }
    const delayS = Math.min(2 ** (this.attempt - 1), 10);
    this.sink.connection({ status: 'reconnecting', attempt: this.attempt, retryInS: delayS });
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.connect();
    }, delayS * 1000);
  }

  private handle(data: unknown) {
    let msg: StreamServerMessage;
    try {
      msg = JSON.parse(String(data));
    } catch {
      return;
    }
    const sink = this.sink;
    if (!sink || !msg || typeof msg !== 'object') return;
    switch (msg.kind) {
      case 'clock':
        if (msg.match_id !== this.opts.matchId) return;
        this.lastT = msg.t_s;
        this.lastBeatAt = this.now();
        this.speed = msg.speed ?? 1;
        this.phase = msg.phase;
        this.period = msg.period;
        this.attempt = 0;
        if (!this.live) {
          this.live = true;
          sink.connection({ status: this.ended ? 'ended' : 'live' });
        }
        sink.clock({ t: msg.t_s, period: msg.period, phase: msg.phase });
        break;
      case 'state':
        if (msg.match_id !== this.opts.matchId) return;
        sink.state({ home: msg.home, away: msg.away, scoreline: msg.scoreline, t_s: msg.t_s });
        break;
      case 'overlay':
        if (isOrder(msg.order) && msg.order.match_id === this.opts.matchId) sink.orders([msg.order]);
        break;
      case 'error':
        if (msg.code === 'stream_ended') {
          // The match is over and the heartbeat goes on: keep the socket and the final state.
          this.ended = true;
          sink.connection({ status: 'ended', code: msg.code });
        } else if (msg.code === 'match_not_found') {
          // Retrying will not help: stay offline until retry().
          this.ended = true;
          this.live = false;
          this.dropSocket();
          sink.connection({ status: 'offline', code: msg.code });
        } else {
          // server_error: "the stream failed, subscribe again".
          this.live = false;
          this.dropSocket();
          this.scheduleReconnect();
        }
        break;
    }
  }

  /** Heartbeat watchdog and local clock extrapolation. Exposed for tests. */
  tick() {
    const sink = this.sink;
    if (!sink || !this.live) return;
    const sinceBeat = this.now() - this.lastBeatAt;
    // After stream_ended the clock stays at the end; a silent socket is no reason to alarm anyone.
    if (this.ended) return;
    if (sinceBeat > HEARTBEAT_TIMEOUT_MS) {
      this.live = false;
      this.dropSocket();
      this.scheduleReconnect();
      return;
    }
    if (this.phase === 'live') {
      const ahead = Math.min((sinceBeat / 1000) * this.speed, MAX_EXTRAPOLATION_S);
      sink.clock({ t: this.lastT + ahead, period: this.period, phase: this.phase });
    }
  }
}

function isOrder(value: unknown): value is OverlayOrder {
  const o = value as OverlayOrder | null;
  return !!o && typeof o.overlay_id === 'string' && typeof o.show_at_s === 'number' && typeof o.type === 'string' && typeof o.slot === 'string';
}
