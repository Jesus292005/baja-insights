import type { Language, Mode } from '../contracts/overlay';
import { parseClockParam } from './parse';

/**
 * Runtime options from the URL, so the same build serves the web app and the broadcast overlay:
 *
 *   /                       web app
 *   /broadcast              1920×1080 overlay on a transparent page (OBS browser source, vMix…)
 *
 *   ?mode=fan|analyst  ?lang=es|en
 *   ?source=replay|live  ?ws=wss://…   (default: replay; live uses ?ws or VITE_STREAM_URL)
 *   ?speed=60  ?skip=0|1  ?autoplay=0|1  ?t=10:50   (replay only)
 *   ?bug=1                            (broadcast only: draw the score bug)
 *
 * Replay is the default on purpose: the deployed stream has one shared clock, so a viewer who
 * opens the link at minute 70 would see minute 70. The replay starts where the viewer wants.
 */
export type SourceKind = 'replay' | 'live';

export interface AppConfig {
  view: 'web' | 'broadcast';
  mode: Mode | null;
  lang: Language | null;
  source: SourceKind;
  /** WebSocket of the stream service, if one is configured. */
  streamUrl: string | null;
  speed: number;
  skip: boolean;
  autoplay: boolean;
  startAt: number;
  bug: boolean;
}

export function readConfig(loc: Pick<Location, 'pathname' | 'search'> = window.location): AppConfig {
  const q = new URLSearchParams(loc.search);
  const streamUrl = q.get('ws') || (import.meta.env.VITE_STREAM_URL as string | undefined) || null;
  const wantsLive = q.get('source') === 'live' || q.get('source') === 'ws';
  const mode = q.get('mode');
  const lang = q.get('lang');
  const speed = Number(q.get('speed'));
  return {
    view: /\/broadcast\/?$/.test(loc.pathname) ? 'broadcast' : 'web',
    mode: mode === 'fan' || mode === 'analyst' ? mode : null,
    lang: lang === 'es' || lang === 'en' ? lang : null,
    source: wantsLive && streamUrl ? 'live' : 'replay',
    streamUrl,
    speed: Number.isFinite(speed) && speed >= 1 ? Math.min(speed, 120) : 60,
    skip: q.get('skip') !== '0',
    autoplay: q.get('autoplay') !== '0',
    startAt: parseClockParam(q.get('t')),
    bug: q.get('bug') === '1',
  };
}

/** Same page with another source, keeping mode, language and the rest of the query. */
export function hrefWithSource(source: SourceKind, loc: Pick<Location, 'pathname' | 'search'> = window.location): string {
  const q = new URLSearchParams(loc.search);
  q.set('source', source);
  if (source === 'live') q.delete('t');
  return `${loc.pathname}?${q.toString()}`;
}
