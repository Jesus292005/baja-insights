import { useEffect, useMemo, useState } from 'react';
import { usePersisted } from '../app/usePersisted';
import { useMatchRuntime } from '../app/useMatchRuntime';
import { hrefWithSource, type AppConfig } from '../app/config';
import { BrandLogo } from '../components/BrandLogo';
import { AskTheMatch } from '../components/rail/AskTheMatch';
import { CardPanel, DuelPanel, MomentsPanel, MvpRacePanel } from '../components/rail/panels';
import {
  ConnectionBanner, ConnectionPill, LanguageToggle, MatchBug, ModeToggle, ReplayControls, SourceToggle, ThemeToggle,
} from '../components/shell/shell';
import { CardBand } from '../components/stage/CardBand';
import { Stage } from '../components/stage/Stage';
import type { Language, Mode } from '../contracts/overlay';
import { demoMatch, roster } from '../data/match';
import { PrefsProvider } from '../i18n/prefs';
import { strings } from '../i18n/strings';
import { mvpAt } from '../logic/derive';
import { playAt, playOf } from '../logic/play';
import { PlayLegend } from '../components/stage/PlayLegend';

export function WebApp({ config }: { config: AppConfig }) {
  const [mode, setMode] = usePersisted<Mode>('bi.mode', 'fan', ['fan', 'analyst'], config.mode);
  // English by default. The key changed with that default, so a language stored before starts in English once.
  const [lang, setLang] = usePersisted<Language>('bi.lang.v2', 'en', ['es', 'en'], config.lang);
  // Dark by default, whatever the system theme. New key for the same reason as the language.
  const [theme, setTheme] = usePersisted<'light' | 'dark'>('bi.theme.v2', 'dark', ['light', 'dark']);
  const rt = useMatchRuntime(config, mode, lang);
  // The moment opened in the list, by overlay id. Its play stays on the pitch while it is open.
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = lang;
    document.title = `${strings[lang].app.name} · ${demoMatch.teams.match.home} – ${demoMatch.teams.match.away}`;
  }, [theme, lang]);

  const { snap, orders, t, showing, loading, stale, replay, replayState } = rt;
  const s = strings[lang];
  const leader = useMemo(() => mvpAt(orders, t).ranking?.[0]?.player ?? null, [orders, t]);
  // An opened moment draws its own play; otherwise the latest one stays on the pitch.
  const latestPlay = useMemo(() => playAt(orders, t, demoMatch.playEvents, roster), [orders, t]);
  const openOrder = useMemo(() => orders.find((o) => o.overlay_id === open) ?? null, [orders, open]);
  const openPlay = useMemo(() => (openOrder ? playOf(openOrder, demoMatch.playEvents, roster) : null), [openOrder]);
  const play = openPlay ?? latestPlay;
  const cinemaHref = `/cine?mode=${mode}&lang=${lang}${config.source === 'replay' ? `&t=${Math.floor(t)}&autoplay=0` : '&source=live'}`;
  const broadcastHref = `/broadcast?mode=${mode}&lang=${lang}&bug=1${config.source === 'replay' ? `&t=${Math.floor(t)}` : '&source=live'}`;

  return (
    <PrefsProvider mode={mode} lang={lang}>
      <a className="skip-link" href="#match">{s.app.skipToMatch}</a>
      <header className="topbar">
        <div className="brand">
          <BrandLogo className="brand-logo" label={s.app.name} />
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
          <CardBand showing={showing} orders={orders} />
          <Stage showing={showing} orders={orders} variant="web" graphics={false} play={play} />
          <PlayLegend play={play} variant="web" />
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
          <MomentsPanel
            orders={orders}
            t={t}
            stale={stale}
            loading={loading}
            open={open}
            onToggle={(o) => setOpen((id) => (id === o.overlay_id ? null : o.overlay_id))}
          />
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
