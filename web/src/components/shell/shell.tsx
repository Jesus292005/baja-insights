import type { Language, Mode } from '../../contracts/overlay';
import { roster } from '../../data/match';
import { usePrefs } from '../../i18n/prefs';
import { clock, t } from '../../i18n/strings';
import type { ReplayState } from '../../stream/replaySource';
import type { ClockUpdate, ConnectionInfo, MatchState } from '../../stream/types';
import { TeamChip } from '../common';

/* ---------- Score bug ---------- */

export function MatchBug({ state, clockUpdate, variant }: { state: MatchState | null; clockUpdate: ClockUpdate | null; variant: 'web' | 'broadcast' }) {
  const { s } = usePrefs();
  const phase = clockUpdate?.phase;
  const phaseLabel = phase === 'half_time' ? s.status.halfTime : phase === 'full_time' ? s.status.fullTime : phase === 'pre' ? s.status.preMatch : null;
  return (
    <div className={`bug bug-${variant}`} aria-label={state ? `${state.home} ${state.scoreline.home}, ${state.away} ${state.scoreline.away}` : s.status.connecting}>
      <span className="bug-team"><TeamChip team={roster.home} /></span>
      <span className="bug-score">
        {state ? (
          <>
            {state.scoreline.home}<span aria-hidden="true">–</span>{state.scoreline.away}
          </>
        ) : (
          <span className="skeleton-inline" aria-hidden="true" />
        )}
      </span>
      <span className="bug-team"><TeamChip team={roster.away} /></span>
      <span className="bug-clock">{clockUpdate ? clock(clockUpdate.t) : '—'}</span>
      {phaseLabel && <span className="bug-phase">{phaseLabel}</span>}
    </div>
  );
}

/* ---------- Connection ---------- */

export function ConnectionPill({ info }: { info: ConnectionInfo }) {
  const { s } = usePrefs();
  const label = {
    connecting: s.status.connecting,
    live: s.status.live,
    reconnecting: s.status.reconnecting.split('.')[0],
    offline: info.code === 'stream_ended' ? s.status.ended : s.status.offline,
    replay: s.status.replay,
  }[info.status];
  return <span className={`pill pill-${info.status}`}>{label}</span>;
}

export function ConnectionBanner({ info, lastDataS, onRetry }: { info: ConnectionInfo; lastDataS: number | null; onRetry: () => void }) {
  const { s } = usePrefs();
  if (info.status !== 'reconnecting' && info.status !== 'offline') return null;
  const at = clock(lastDataS ?? 0);
  if (info.status === 'reconnecting') {
    return (
      <div className="banner banner-warn" role="status">
        <span>{lastDataS === null ? s.status.connecting : t(s.status.reconnecting, { clock: at })}</span>
        {info.retryInS !== undefined && <span className="mono">{t(s.status.reconnectingIn, { seconds: info.retryInS })}</span>}
      </div>
    );
  }
  return (
    <div className="banner banner-error" role="alert">
      <span>
        <b>{info.code === 'stream_ended' ? s.status.ended : s.status.offline}</b> {lastDataS !== null && t(s.status.offlineBody, { clock: at })}
      </span>
      {info.code !== 'stream_ended' && (
        <button type="button" className="btn" onClick={onRetry}>{s.status.retry}</button>
      )}
    </div>
  );
}

/* ---------- Toggles ---------- */

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: { value: T; label: string; hint?: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} title={o.hint} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ModeToggle({ value, onChange }: { value: Mode; onChange: (m: Mode) => void }) {
  const { s } = usePrefs();
  return (
    <Segmented
      label={s.mode.label}
      value={value}
      onChange={onChange}
      options={[
        { value: 'fan', label: s.mode.fan, hint: s.mode.fanHint },
        { value: 'analyst', label: s.mode.analyst, hint: s.mode.analystHint },
      ]}
    />
  );
}

export function LanguageToggle({ value, onChange }: { value: Language; onChange: (l: Language) => void }) {
  const { s } = usePrefs();
  return (
    <Segmented
      label={s.language.label}
      value={value}
      onChange={onChange}
      options={[
        { value: 'es', label: 'ES', hint: s.language.es },
        { value: 'en', label: 'EN', hint: s.language.en },
      ]}
    />
  );
}

export function ThemeToggle({ value, onChange }: { value: 'light' | 'dark'; onChange: (v: 'light' | 'dark') => void }) {
  const { s } = usePrefs();
  return (
    <Segmented
      label={s.app.theme}
      value={value}
      onChange={onChange}
      options={[
        { value: 'light', label: s.app.themeLight },
        { value: 'dark', label: s.app.themeDark },
      ]}
    />
  );
}

/* ---------- Replay controls ---------- */

export interface ReplayControlsProps {
  state: ReplayState;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (t: number) => void;
  onSpeed: (speed: number) => void;
  onSkip: (skip: boolean) => void;
}

const SPEEDS = [1, 10, 30, 60];

export function ReplayControls({ state, onPlay, onPause, onSeek, onSpeed, onSkip }: ReplayControlsProps) {
  const { s } = usePrefs();
  return (
    <div className="replay" role="group" aria-label={s.replay.label}>
      <button type="button" className="btn btn-icon" onClick={state.playing ? onPause : onPlay} aria-label={state.playing ? s.replay.pause : s.replay.play}>
        <span aria-hidden="true">{state.playing ? '❚❚' : '▶'}</span>
      </button>
      <label className="replay-seek">
        <span className="sr-only">{s.replay.seek}</span>
        <input
          type="range"
          min={0}
          max={Math.ceil(state.end)}
          step={1}
          value={Math.floor(state.t)}
          aria-valuetext={clock(state.t)}
          onChange={(e) => onSeek(Number(e.target.value))}
        />
      </label>
      <span className="replay-clock mono">{clock(state.t)}</span>
      <label className="field field-inline">
        <span>{s.replay.speed}</span>
        <select value={state.speed} onChange={(e) => onSpeed(Number(e.target.value))}>
          {SPEEDS.map((x) => <option key={x} value={x}>{x}×</option>)}
        </select>
      </label>
      <label className="check">
        <input type="checkbox" checked={state.skip} onChange={(e) => onSkip(e.target.checked)} />
        <span>{s.replay.skip}</span>
      </label>
    </div>
  );
}
