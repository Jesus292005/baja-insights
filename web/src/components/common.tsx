import type { ReactNode } from 'react';
import type { TeamRef } from '../data/roster';
import { usePrefs } from '../i18n/prefs';
import { clock, t } from '../i18n/strings';

/** Team code on its own colour. Always text, never colour alone. */
export function TeamChip({ team }: { team: TeamRef | undefined }) {
  if (!team) return null;
  return (
    <span className={`chip chip-${team.side}`} title={team.name}>
      {team.short}
    </span>
  );
}

/** "Dato del 63:09" next to any persistent number. */
export function AsOf({ s, stale }: { s: number; stale?: boolean }) {
  const { s: str } = usePrefs();
  return <span className={`as-of${stale ? ' as-of-stale' : ''}`}>{t(str.status.asOf, { clock: clock(s) })}</span>;
}

export function Evidence({ ids, tools }: { ids?: number[]; tools?: string[] }) {
  const { s } = usePrefs();
  if (!ids?.length && !tools?.length) return null;
  return (
    <div className="evidence">
      <span className="evidence-label">{s.evidence.label}</span>
      {tools?.map((x) => <code key={x} className="evidence-chip">{x}</code>)}
      {ids?.map((id) => <code key={id} className="evidence-chip">#{id}</code>)}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

/** Long dash with an accessible name, for a number that did not arrive. */
export function NoData() {
  const { s } = usePrefs();
  return <span aria-label={s.noData.a11y}>{s.noData.short}</span>;
}
