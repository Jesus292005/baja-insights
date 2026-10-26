import { useEffect, useMemo, useState } from 'react';
import { usePersisted } from '../app/usePersisted';
import { useMatchRuntime } from '../app/useMatchRuntime';
import { hrefWithSource, type AppConfig } from '../app/config';
import { AskTheMatch } from '../components/rail/AskTheMatch';
import { CardPanel, DuelPanel, MomentsPanel, MvpRacePanel } from '../components/rail/panels';
import {
  ConnectionBanner, ConnectionPill, LanguageToggle, MatchBug, ModeToggle, ReplayControls, SourceToggle, ThemeToggle,
} from '../components/shell/shell';
import { Stage } from '../components/stage/Stage';
import type { Language, Mode, OverlayOrder } from '../contracts/overlay';
import { demoMatch } from '../data/match';
import { PrefsProvider } from '../i18n/prefs';
import { strings } from '../i18n/strings';
import { mvpAt } from '../logic/derive';
import type { Showing } from '../logic/plan';

const prefersDark = () => {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return true;
  }
};

/** Re-renders every frame while `active`, for the replayed moment's tide line. */
function useFrame(active: boolean) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    let id = requestAnimationFrame(function loop() {
      setTick((n) => n + 1);
      id = requestAnimationFrame(loop);
    });
    return () => cancelAnimationFrame(id);
  }, [active]);
}

export function WebApp({ config }: { config: AppConfig }) {
  const [mode, setMode] = usePersisted<Mode>('bi.mode', 'fan', ['fan', 'analyst'], config.mode);
  // English by default. The key changed with that default, so a language stored before starts in English once.
  const [lang, setLang] = usePersisted<Language>('bi.lang.v2', 'en', ['es', 'en'], config.lang);
  const [theme, setTheme] = usePersisted<'light' | 'dark'>('bi.theme', prefersDark() ? 'dark' : 'light', ['light', 'dark']);
  const rt = useMatchRuntime(config, mode, lang);
  const [pinned, setPinned] = useState<{ order: OverlayOrder; startedAt: number } | null>(null);
  useFrame(pinned !== null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = lang;
    document.title = `${strings[lang].app.name} · ${demoMatch.teams.match.home} – ${demoMatch.teams.match.away}`;
  }, [theme, lang]);

  let override: Showing | null = null;
  if (pinned) {
    const elapsed = (performance.now() - pinned.startedAt) / 1000;
    if (elapsed < pinned.order.duration_s) override = { order: pinned.order, elapsed };
  }
  useEffect(() => {
    if (!pinned) return;
    const id = setTimeout(() => setPinned(null), pinned.order.duration_s * 1000 + 50);
    return () => clearTimeout(id);
  }, [pinned]);

  const { snap, orders, t, showing, loading, stale, replay, replayState } = rt;
  const s = strings[lang];
  const leader = useMemo(() => mvpAt(orders, t).ranking?.[0]?.player ?? null, [orders, t]);
  const cinemaHref = `/cine?mode=${mode}&lang=${lang}${config.source === 'replay' ? `&t=${Math.floor(t)}&autoplay=0` : '&source=live'}`;
  const broadcastHref = `/broadcast?mode=${mode}&lang=${lang}&bug=1${config.source === 'replay' ? `&t=${Math.floor(t)}` : '&source=live'}`;

  return (
    <PrefsProvider mode={mode} lang={lang}>
      <a className="skip-link" href="#match">{s.app.skipToMatch}</a>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">{s.app.name}</span>
          <span className="brand-tag">{s.app.tagline}</span>
        </div>
        <MatchBug state={snap.state} clockUpdate={snap.clock} variant="web" />
        <ConnectionPill info={snap.connection} />
        <div className="topbar-controls">
          <SourceToggle
            value={config.source}
            liveAvailable={config.streamUrl !== null}
            onChange={(v) => {
              if (v !== config.source) window.location.assign(hrefWithSource(v));
            }}
          />
          <ModeToggle value={mode} onChange={setMode} />
          <LanguageToggle value={lang} onChange={setLang} />
          <ThemeToggle value={theme} onChange={setTheme} />
          <a className="btn btn-ghost" href={cinemaHref} target="_blank" rel="noreferrer">{s.cinema.link}</a>
          <a className="btn btn-ghost" href={broadcastHref} target="_blank" rel="noreferrer">{s.app.broadcastLink}</a>
        </div>
      </header>
      <ConnectionBanner info={snap.connection} lastDataS={snap.lastDataS} onRetry={rt.retry} />

      <main id="match" className="layout" tabIndex={-1}>
        <h1 className="sr-only">
          {demoMatch.teams.match.home} – {demoMatch.teams.match.away} · {s.app.name}
        </h1>
        <aside className="rail rail-left" aria-label={s.app.matchPanels}>
          <MvpRacePanel orders={orders} t={t} stale={stale} loading={loading} />
          <DuelPanel orders={orders} t={t} stale={stale} loading={loading} />
          <CardPanel orders={orders} t={t} stale={stale} loading={loading} />
        </aside>
        <div className="main-col">
          <Stage showing={showing} orders={orders} variant="web" override={override} />
          {replay && replayState && (
            <ReplayControls
              state={replayState}
              onPlay={() => replay.play()}
              onPause={() => replay.pause()}
              onSeek={(x) => replay.seek(x)}
              onSpeed={(x) => replay.setSpeed(x)}
              onSkip={(x) => replay.setSkip(x)}
            />
          )}
          <MomentsPanel orders={orders} t={t} stale={stale} loading={loading} onSelect={(o) => setPinned({ order: o, startedAt: performance.now() })} />
        </div>
        <aside className="rail rail-right" aria-label={s.chat.title}>
          <AskTheMatch
            matchId={demoMatch.matchId}
            t={t}
            connection={snap.connection.status}
            leader={leader}
            onShowOrder={(order) => rt.inject([order])}
          />
        </aside>
      </main>
      <footer className="footer">
        {s.app.fiction} {demoMatch.teams.match.competition} · {demoMatch.teams.match.venue}
      </footer>
    </PrefsProvider>
  );
}
