import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { AppConfig } from '../app/config';
import { useMatchRuntime } from '../app/useMatchRuntime';
import { usePersisted } from '../app/usePersisted';
import { usePositions } from '../data/positions';
import { MatchBug } from '../components/shell/shell';
import { Stage } from '../components/stage/Stage';
import type { Language, Mode } from '../contracts/overlay';
import { PrefsProvider } from '../i18n/prefs';
import { strings } from '../i18n/strings';
import { demoMatch, roster } from '../data/match';
import { forViewer, momentsAt } from '../logic/derive';
import { drawnIn, halfOf, playOnScreen } from '../logic/play';
import { HalfTimeNotice, useHalfTime } from '../components/stage/HalfTime';
import { PlayLegend } from '../components/stage/PlayLegend';

/**
 * Cinema mode (/cine): the 1920×1080 stage on a black page, with the pitch and the score bug,
 * for screen recording. No rail and no controls: everything is on the keyboard, so mode and
 * language can be switched on camera. Mode and language stay in the URL, so a reload keeps them.
 */

/** Seconds of lead before a moment, so the graphic enters on camera. */
const LEAD_S = 2;

/** Room of the mode badge at the top centre of the canvas (.cinema-badge), kept free of cards. */
const BADGE_BOX = { x: 770, y: 40, w: 380, h: 74 };

export function CinemaView({ config }: { config: AppConfig }) {
  const [mode, setMode] = useState<Mode>(config.mode ?? 'fan');
  const [lang, setLang] = useState<Language>(config.lang ?? 'en');
  const [badge, setBadge] = useState(true);
  // Same choice as the web app: the illustrative players are on unless hidden (J).
  const [showPlayers, setShowPlayers] = usePersisted<'on' | 'off'>('bi.players.v1', 'on', ['on', 'off']);
  const [help, setHelp] = useState(false);
  const [hint, setHint] = useState(true);
  const [pulse, setPulse] = useState(0);
  const rt = useMatchRuntime(config, mode, lang);
  const s = strings[lang];

  // Moment start times for N / P. The replay hands orders over just before they are due, like
  // the stream, so the whole demo match is read here; live mode has no seeking.
  const momentTimes = useMemo(
    () =>
      [...new Set(momentsAt(forViewer(demoMatch.overlays, mode, lang), Infinity, Infinity).map((o) => o.show_at_s))].sort(
        (a, b) => a - b,
      ),
    [mode, lang],
  );

  useEffect(() => {
    const root = document.documentElement;
    delete root.dataset.theme;
    root.dataset.view = 'cinema';
    root.lang = lang;
    const q = new URLSearchParams(window.location.search);
    q.set('mode', mode);
    q.set('lang', lang);
    window.history.replaceState(null, '', `${window.location.pathname}?${q.toString()}`);
  }, [mode, lang]);

  useEffect(() => {
    const id = setTimeout(() => setHint(false), 4000);
    return () => clearTimeout(id);
  }, []);

  const tRef = useRef(rt.t);
  tRef.current = rt.t;

  const onKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const replay = rt.replay;
      const t = tRef.current;
      const key = e.key.toLowerCase();
      let handled = true;
      if (e.code === 'Space' && replay) {
        if (replay.getState().playing) replay.pause();
        else replay.play();
      } else if (key === 'm') {
        setMode((m) => (m === 'fan' ? 'analyst' : 'fan'));
        setPulse((n) => n + 1);
      } else if (key === 'l') {
        setLang((l) => (l === 'es' ? 'en' : 'es'));
        setPulse((n) => n + 1);
      } else if (key === 'n' && replay) {
        const next = momentTimes.find((x) => x - LEAD_S > t + 0.5);
        if (next !== undefined) replay.seek(next - LEAD_S);
      } else if (key === 'p' && replay) {
        const prev = [...momentTimes].reverse().find((x) => x - LEAD_S < t - 3);
        replay.seek(prev !== undefined ? prev - LEAD_S : 0);
      } else if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && replay) {
        const step = (e.shiftKey ? 60 : 10) * (e.key === 'ArrowRight' ? 1 : -1);
        replay.seek(t + step);
      } else if (key === 'b') {
        setBadge((v) => !v);
      } else if (key === 'j') {
        setShowPlayers(showPlayers === 'on' ? 'off' : 'on');
      } else if (key === 'h' || (key === 'escape' && help)) {
        setHelp((v) => (key === 'escape' ? false : !v));
        setHint(false);
      } else if (key === 'f') {
        if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
        else void document.documentElement.requestFullscreen?.().catch(() => {});
      } else {
        handled = false;
      }
      if (handled) e.preventDefault();
    },
    [rt.replay, momentTimes, help, showPlayers, setShowPlayers],
  );

  useEffect(() => {
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onKey]);

  const halfTime = useHalfTime(rt.t, rt.snap.clock?.phase);
  const positions = usePositions(showPlayers === 'on');
  // Drawn in the clock's half, so the teams swap ends at 45:00.
  // The play of the card on screen, only while it is up.
  const onScreen = Object.values(rt.showing).filter((x): x is NonNullable<typeof x> => !!x);
  const play = drawnIn(playOnScreen(onScreen, demoMatch.playEvents, roster), halfOf(rt.t));

  return (
    <PrefsProvider mode={mode} lang={lang}>
      <main className="cinema" aria-label={s.cinema.link}>
        <Stage
          showing={rt.showing}
          orders={rt.orders}
          variant="broadcast"
          backdrop
          play={play}
          half={halfOf(rt.t)}
          players={positions ? { file: positions, t: rt.t, frozen: false } : null}
          reserved={badge ? [BADGE_BOX] : []}
          bug={
            <div className="slot-bug">
              <MatchBug state={rt.snap.state} clockUpdate={rt.snap.clock} variant="broadcast" />
            </div>
          }
        >
          {badge && (
            <p key={pulse} className={`cinema-badge cinema-badge-${mode}`} aria-live="polite">
              {mode === 'fan' ? s.cinema.badgeFan : s.cinema.badgeAnalyst} · {lang.toUpperCase()}
            </p>
          )}
          <PlayLegend play={play} variant="canvas" />
          {halfTime && <HalfTimeNotice scoreline={rt.snap.state?.scoreline ?? null} />}
          {hint && !help && <p className="cinema-hint">{s.cinema.hint}</p>}
          {help && (
            <div className="cinema-help" role="dialog" aria-label={s.cinema.helpTitle}>
              <h2>{s.cinema.helpTitle}</h2>
              <dl>
                {s.cinema.keys.map(([k, v]) => (
                  <div key={k}>
                    <dt><kbd>{k}</kbd></dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </Stage>
      </main>
    </PrefsProvider>
  );
}
