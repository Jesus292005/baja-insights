import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePersisted } from '../app/usePersisted';
import { useMatchRuntime } from '../app/useMatchRuntime';
import { hrefWithSource, replayQuery, type AppConfig } from '../app/config';
import { BrandLogo } from '../components/BrandLogo';
import { AskTheMatch } from '../components/rail/AskTheMatch';
import { CardPanel, DuelPanel, MomentsPanel, MvpRacePanel } from '../components/rail/panels';
import {
  ConnectionBanner, ConnectionPill, LanguageToggle, MatchBug, ModeToggle, ReplayControls, SourceToggle, ThemeToggle,
} from '../components/shell/shell';
import { CardBand } from '../components/stage/CardBand';
import { PlayerCorner } from '../components/stage/PlayerCorner';
import { hasPositions, useDeadBall, usePositions } from '../data/positions';
import { Stage } from '../components/stage/Stage';
import type { Language, Mode } from '../contracts/overlay';
import { demoMatch, roster } from '../data/match';
import { PrefsProvider } from '../i18n/prefs';
import { strings } from '../i18n/strings';
import { mvpAt } from '../logic/derive';
import { drawnIn, halfOf, playOf, playOnScreen } from '../logic/play';
import type { Showing } from '../logic/plan';
import { HalfTimeNotice, useHalfTime } from '../components/stage/HalfTime';
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
  // The latest play follows the clock's half, so the teams swap ends at 45:00; an opened moment keeps its own.
  const half = halfOf(t);
  // The play of the card on screen, only while it is up; it follows the clock's half.
  const onScreen = useMemo(() => Object.values(showing).filter((x): x is Showing => !!x), [showing]);
  const latestPlay = useMemo(() => drawnIn(playOnScreen(onScreen, demoMatch.playEvents, roster), half), [onScreen, half]);
  const halfTime = useHalfTime(t, snap.clock?.phase);
  const openOrder = useMemo(() => orders.find((o) => o.overlay_id === open) ?? null, [orders, open]);
  const openPlay = useMemo(() => (openOrder ? playOf(openOrder, demoMatch.playEvents, roster) : null), [openOrder]);
  const play = openPlay ?? latestPlay;
  // Illustrative players: at the clock's second, or frozen at the last action of an opened moment.
  const [showPlayers, setShowPlayers] = usePersisted<'on' | 'off'>('bi.players.v1', 'on', ['on', 'off']);
  // Loaded even with the players hidden: its set pieces let the replay pass dead balls quickly.
  const positionsFile = usePositions();
  useDeadBall(replay, positionsFile);
  const positions = showPlayers === 'on' ? positionsFile : null;
  // A player picked on the pitch: their card shows in its top-right corner until closed.
  const [picked, setPicked] = useState<string | null>(null);
  const closePicked = useCallback(() => setPicked(null), []);
  useEffect(() => {
    if (!positions) setPicked(null);
  }, [positions]);
  const playersT = openPlay ? Math.max(...openPlay.links.map((l) => l.t_s)) : t;
  // Both views carry the replay over as it is: same second and speed, still playing if it was.
  const carry = config.source === 'replay' ? replayQuery(t, replayState) : '&source=live';
  const cinemaHref = `/cine?mode=${mode}&lang=${lang}${carry}`;
  const broadcastHref = `/broadcast?mode=${mode}&lang=${lang}&bug=1${carry}`;

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
          {/* The picked player's card: over the pitch's top-right corner, or under it on a phone. */}
          <div className="pitch-wrap">
            <Stage
              showing={showing}
              orders={orders}
              variant="web"
              graphics={false}
              play={play}
              half={half}
              // Held still while a moment is open or the replay is paused, so they never drift past the clock.
              players={
                positions
                  ? { file: positions, t: playersT, frozen: !!openPlay || replayState?.playing === false, onSelect: setPicked, selected: picked }
                  : null
              }
              onPitchClick={picked ? closePicked : undefined}
            >
              {halfTime && <HalfTimeNotice scoreline={snap.state?.scoreline ?? null} />}
            </Stage>
            {picked && positions && (
              <div className="stage-corner">
                <PlayerCorner player={picked} orders={orders} t={playersT} onClose={closePicked} />
              </div>
            )}
          </div>
          <PlayLegend play={play} variant="web" />
          {hasPositions && (
            <label className="players-toggle">
              <input type="checkbox" checked={showPlayers === 'on'} onChange={(e) => setShowPlayers(e.target.checked ? 'on' : 'off')} />
              <span>{s.players.toggle}</span>
              <span className="players-note">{s.players.note}</span>
            </label>
          )}
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
