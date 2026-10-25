import { roster } from '../data/match';
import { usePrefs } from '../i18n/prefs';
import { signed, surname, t } from '../i18n/strings';
import { TeamChip } from './common';

export interface DuelMeterProps {
  playerA: string;
  playerB: string;
  /** Engine value −1..1. Positive: player A (home, left) ahead. */
  bar: number;
  size: 'web' | 'broadcast';
  stale?: boolean;
}

const EVEN = 0.05;

/** Who is ahead in words. The bar only moves; the number is shown as sent. */
export function duelVerdict(bar: number, playerA: string, playerB: string, template: { even: string; ahead: string }) {
  if (Math.abs(bar) < EVEN) return template.even;
  return t(template.ahead, { player: surname(bar > 0 ? playerA : playerB) });
}

export function DuelMeter({ playerA, playerB, bar, size, stale }: DuelMeterProps) {
  const { s, mode, lang } = usePrefs();
  const a = roster.player(playerA);
  const b = roster.player(playerB);
  const half = Math.min(Math.abs(bar), 1) * 50;
  const winner = bar >= 0 ? 'home' : 'away';
  const verdict = duelVerdict(bar, playerA, playerB, s.duel);
  return (
    <div className={`duel duel-${size}${stale ? ' is-stale' : ''}`}>
      <div className="duel-names">
        <span className="duel-name"><TeamChip team={a?.team} />{playerA}</span>
        <span className="duel-name duel-name-b">{playerB}<TeamChip team={b?.team} /></span>
      </div>
      <div
        className="duel-track"
        role="meter"
        aria-valuemin={-1}
        aria-valuemax={1}
        aria-valuenow={bar}
        aria-valuetext={verdict}
        aria-label={`${s.duel.title}: ${playerA} – ${playerB}`}
      >
        <span
          className={`duel-fill duel-fill-${winner}`}
          style={{ left: `${bar >= 0 ? 50 - half : 50}%`, width: `${half}%` }}
        />
        <span className="duel-knob" style={{ left: `${50 - Math.max(-1, Math.min(1, bar)) * 50}%` }} />
      </div>
      <div className="duel-verdict">
        <strong>{verdict}</strong>
        {mode === 'analyst' && <span className="mono">{s.duel.bar} {signed(bar, lang)}</span>}
      </div>
    </div>
  );
}
