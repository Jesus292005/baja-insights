import type { Language, Mode } from '../contracts/overlay';
import { parseClockParam } from './parse';

/**
 * Runtime options from the URL, so the same build serves the web app and the broadcast overlay:
 *
 *   /                       web app
 *   /broadcast              1920×1080 overlay on a transparent page (OBS browser source, vMix…)
 *
 *   ?mode=fan|analyst  ?lang=es|en
 *   ?source=replay|ws  ?ws=wss://…   (default: replay, or ws when VITE_STREAM_URL is set)
 *   ?speed=60  ?skip=0|1  ?autoplay=0|1  ?t=10:50   (replay only)
 *   ?bug=1                            (broadcast only: draw the score bug)
 */
export interface AppConfig {
  view: 'web' | 'broadcast';
  mode: Mode | null;
  lang: Language | null;
  source: 'replay' | 'ws';
  wsUrl: string | null;
  speed: number;
  skip: boolean;
  autoplay: boolean;
  startAt: number;
  bug: boolean;
}

export function readConfig(loc: Pick<Location, 'pathname' | 'search'> = window.location): AppConfig {
  const q = new URLSearchParams(loc.search);
  const envWs = (import.meta.env.VITE_STREAM_URL as string | undefined) || null;
  const wsUrl = q.get('ws') || envWs;
  const source = q.get('source') === 'ws' || (q.get('source') !== 'replay' && !!envWs) ? 'ws' : 'replay';
  const mode = q.get('mode');
  const lang = q.get('lang');
  const speed = Number(q.get('speed'));
  return {
    view: /\/broadcast\/?$/.test(loc.pathname) ? 'broadcast' : 'web',
    mode: mode === 'fan' || mode === 'analyst' ? mode : null,
    lang: lang === 'es' || lang === 'en' ? lang : null,
    source: source === 'ws' && wsUrl ? 'ws' : 'replay',
    wsUrl,
    speed: Number.isFinite(speed) && speed >= 1 ? Math.min(speed, 120) : 60,
    skip: q.get('skip') !== '0',
    autoplay: q.get('autoplay') !== '0',
    startAt: parseClockParam(q.get('t')),
    bug: q.get('bug') === '1',
  };
}
