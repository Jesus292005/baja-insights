import { roster } from '../../data/match';
import { usePrefs } from '../../i18n/prefs';
import { clock } from '../../i18n/strings';
import { buildPlay, type LegendKind, type MatchPlay } from '../../logic/play';
import { TeamChip } from '../common';

/**
 * Explains the lines and arrows of the play on the pitch: only the kinds the current play uses,
 * plus the team colours. Web: an HTML strip under the stage. Cinema: one line at the foot of the canvas.
 */

function Swatch({ kind }: { kind: LegendKind }) {
  const team = 'var(--bi-team-home)';
  const common = { width: 34, height: 14, viewBox: '0 0 34 14', 'aria-hidden': true } as const;
  switch (kind) {
    case 'pass':
      return <svg {...common}><line x1="2" y1="7" x2="26" y2="7" stroke={team} strokeWidth="3" /><path d="M24 2 L33 7 L24 12 z" fill={team} /></svg>;
    case 'shot':
      return <svg {...common}><line x1="2" y1="7" x2="26" y2="7" stroke={team} strokeWidth="5" /><path d="M24 1 L34 7 L24 13 z" fill={team} /></svg>;
    case 'cross':
      return <svg {...common}><path d="M2 12 Q16 -2 27 9" fill="none" stroke={team} strokeWidth="3" /><path d="M24 5 L33 11 L23 13 z" fill={team} /></svg>;
    case 'ball':
      return <svg {...common}><line x1="2" y1="7" x2="32" y2="7" stroke="var(--bi-text-muted)" strokeWidth="3" strokeDasharray="1 5" strokeLinecap="round" /></svg>;
    case 'run':
      return <svg {...common}><line x1="2" y1="7" x2="26" y2="7" stroke="var(--bi-accent)" strokeWidth="3" strokeDasharray="7 4" /><path d="M24 2 L33 7 L24 12 z" fill="var(--bi-accent)" /></svg>;
    case 'defender':
      return <svg {...common}><circle cx="6" cy="7" r="4" fill="none" stroke="var(--bi-team-away)" strokeWidth="2" /><line x1="10" y1="7" x2="26" y2="7" stroke="var(--bi-team-away)" strokeWidth="2.5" strokeDasharray="4 3" /><path d="M24 3 L32 7 L24 11 z" fill="var(--bi-team-away)" /></svg>;
    case 'recovery':
      return <svg {...common}><circle cx="17" cy="7" r="6" fill={team} /></svg>;
    case 'duel':
      return <svg {...common}><rect x="12" y="2" width="10" height="10" transform="rotate(45 17 7)" fill={team} /></svg>;
    case 'pressure':
      return <svg {...common}><circle cx="17" cy="7" r="5.5" fill="none" stroke={team} strokeWidth="2.5" /></svg>;
  }
}

export function PlayLegend({ play, variant }: { play: MatchPlay | null; variant: 'web' | 'canvas' }) {
  const { s } = usePrefs();
  if (!play) {
    return variant === 'web' ? <p className="legend legend-web legend-empty">{s.legend.empty}</p> : null;
  }
  const kinds = buildPlay(play.links, play.goal).legend;
  const o = play.order;
  return (
    <section className={`legend legend-${variant}`} aria-label={s.legend.title}>
      {variant === 'web' && (
        <p className="legend-caption">
          <b>{s.legend.title}</b> {s.kicker[o.type]} · {o.title ?? ''} · <span className="mono">{clock(o.show_at_s)}</span>
        </p>
      )}
      <ul>
        {kinds.map((k) => (
          <li key={k}>
            <Swatch kind={k} />
            <span>{s.legend[k]}</span>
          </li>
        ))}
        <li className="legend-teams">
          <span className="legend-team"><i style={{ background: 'var(--bi-team-home)' }} /> <TeamChip team={roster.home} /></span>
          <span className="legend-team"><i style={{ background: 'var(--bi-team-away)' }} /> <TeamChip team={roster.away} /></span>
        </li>
      </ul>
    </section>
  );
}
