import { useMemo, useState, type ReactNode } from 'react';
import type { OverlayOrder } from '../../contracts/overlay';
import { roster } from '../../data/match';
import { usePrefs } from '../../i18n/prefs';
import { cardReasonLabel } from '../../i18n/labels';
import { asSent, attributeLabel, attributeShort, clock, ordinal, positionLabel, signed, t } from '../../i18n/strings';
import { cardAt, duelAt, momentsAt, mvpAt, playersWithChanges } from '../../logic/derive';
import { AsOf, EmptyState, TeamChip } from '../common';
import { DuelMeter } from '../DuelMeter';
import { PlayerCard } from '../PlayerCard';

interface PanelProps {
  /** The viewer's orders (already filtered by mode and language). */
  orders: readonly OverlayOrder[];
  t: number;
  stale: boolean;
  loading: boolean;
}

function RailPanel({ title, aside, children, id }: { title: string; aside?: ReactNode; children: ReactNode; id: string }) {
  return (
    <section className="rail-panel" aria-labelledby={id}>
      <header className="rail-head">
        <h2 id={id}>{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => <span key={i} />)}
    </div>
  );
}

/* ---------- 1. MVP race ---------- */

export function MvpRacePanel({ orders, t: now, stale, loading }: PanelProps) {
  const { s, lang, mode } = usePrefs();
  const view = useMemo(() => mvpAt(orders, now), [orders, now]);
  const size = mode === 'analyst' ? 5 : 3;
  const title = view.rankingIsFinal ? s.mvp.finalTop : s.mvp.title;
  return (
    <RailPanel id="rail-mvp" title={title} aside={view.rankingAsOfS !== null ? <AsOf s={view.rankingAsOfS} stale={stale} /> : view.moves[0] ? <AsOf s={view.moves[0].show_at_s} stale={stale} /> : null}>
      {loading ? (
        <Skeleton rows={size} />
      ) : view.ranking ? (
        <ol className={`race${stale ? ' is-stale' : ''}`}>
          {view.ranking.slice(0, size).map((r) => {
            const p = roster.player(r.player);
            return (
              <li key={r.player} className={r.rank === 1 ? 'is-lead' : ''}>
                <span className="race-pos">{r.rank}</span>
                <span className="race-who">
                  <b>{r.player}</b>
                  <span>
                    <TeamChip team={p?.team} /> {p ? positionLabel[lang][p.position].short : ''}
                  </span>
                </span>
                {mode === 'analyst' && <span className="race-score">{asSent(r.mvp_score, lang)}</span>}
              </li>
            );
          })}
        </ol>
      ) : view.moves.length ? (
        <>
          <ul className={`moves${stale ? ' is-stale' : ''}`}>
            {view.moves.slice(0, size).map((m) => (
              <li key={m.overlay_id}>
                <span className="moves-time">{m.show_at}</span>
                <span className="moves-body">
                  <b>{m.title ?? '—'}</b>
                  <span className="moves-rank">
                    {m.data.previous_rank !== undefined && m.data.previous_rank > m.data.rank
                      ? `▲ ${t(s.mvp.rankUp, { from: ordinal(m.data.previous_rank, lang), to: ordinal(m.data.rank, lang) })}`
                      : t(s.mvp.newEntry, { to: ordinal(m.data.rank, lang) })}
                    {mode === 'analyst' && ` · ${s.mvp.score} ${asSent(m.data.mvp_score, lang)}`}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="note">{s.mvp.partial}</p>
        </>
      ) : (
        <EmptyState>{s.mvp.empty}</EmptyState>
      )}
    </RailPanel>
  );
}

/* ---------- 2. Duel ---------- */

export function DuelPanel({ orders, t: now, stale, loading }: PanelProps) {
  const { s } = usePrefs();
  const view = useMemo(() => duelAt(orders, now), [orders, now]);
  return (
    <RailPanel id="rail-duel" title={s.duel.title} aside={view ? <AsOf s={view.asOfS} stale={stale} /> : null}>
      {loading ? (
        <Skeleton rows={2} />
      ) : view ? (
        <>
          <DuelMeter playerA={view.playerA} playerB={view.playerB} bar={view.bar} size="web" stale={stale} />
          {view.notice?.text && <p className="rail-text">{view.notice.text}</p>}
          <p className="note">{s.duel.legend}</p>
        </>
      ) : (
        <EmptyState>{s.duel.empty}</EmptyState>
      )}
    </RailPanel>
  );
}

/* ---------- 5. Player card ---------- */

export function CardPanel({ orders, t: now, stale, loading }: PanelProps) {
  const { s, lang, mode } = usePrefs();
  const changed = useMemo(() => playersWithChanges(orders, now), [orders, now]);
  const [picked, setPicked] = useState<string | null>(null);
  // Follow the player picked, else the latest card that changed, else the first home starter.
  const name = picked ?? changed[0] ?? roster.players.find((p) => p.starter)?.name ?? '';
  const card = useMemo(() => cardAt(roster, orders, name, now), [orders, name, now]);
  const options = useMemo(() => {
    const rest = roster.players.filter((p) => !changed.includes(p.name));
    return [...changed.map((n) => roster.player(n)!).filter(Boolean), ...rest];
  }, [changed]);

  return (
    <RailPanel id="rail-card" title={s.card.title} aside={card?.changes.length ? <AsOf s={card.changes[card.changes.length - 1].atS} stale={stale} /> : null}>
      <label className="field">
        <span>{s.card.follow}</span>
        <select value={name} onChange={(e) => setPicked(e.target.value)}>
          {options.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name} · {p.team.short} · {positionLabel[lang][p.position].short}
            </option>
          ))}
        </select>
      </label>
      {loading ? (
        <Skeleton rows={4} />
      ) : card ? (
        <div className="card-row">
          <PlayerCard
            player={card.player}
            attributes={card.attributes}
            overall={card.overall}
            overallFrom={card.overallFrom}
            changed={new Set(card.changes.map((c) => c.attribute))}
            highlight={card.changes[card.changes.length - 1]?.attribute}
            size="md"
          />
          <div className="card-changes">
            <h3>{s.card.changes}</h3>
            {card.changes.length ? (
              <ul>
                {[...card.changes].reverse().map((c) => (
                  <li key={`${c.atS}-${c.attribute}`}>
                    <b>
                      <abbr title={attributeLabel[lang][c.attribute]}>{attributeShort[lang][c.attribute]}</abbr> {c.from} → {c.to}
                    </b>{' '}
                    <span className="up">+{c.delta}</span> · <span className="mono">{clock(c.atS)}</span>
                    {c.overall_from !== undefined && c.overall_to !== undefined && c.overall_from !== c.overall_to && (
                      <span className="card-overall">
                        {s.card.overall} {c.overall_from} → <b className="up">{c.overall_to}</b>
                      </span>
                    )}
                    {mode === 'analyst' && (cardReasonLabel(c, lang) ?? c.title) && (
                      <span className="card-reason">{cardReasonLabel(c, lang) ?? c.title}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState>{s.card.base}. {s.card.noChanges}</EmptyState>
            )}
          </div>
        </div>
      ) : (
        <EmptyState>{s.noData.a11y}</EmptyState>
      )}
    </RailPanel>
  );
}

/* ---------- Moments ---------- */

export function MomentsPanel({ orders, t: now, onSelect }: PanelProps & { onSelect: (o: OverlayOrder) => void }) {
  const { s, lang, mode } = usePrefs();
  const items = useMemo(() => momentsAt(orders, now), [orders, now]);
  return (
    <section className="moments" aria-labelledby="moments-title">
      <h2 id="moments-title">{s.timeline.title}</h2>
      {items.length ? (
        <ol>
          {items.map((o) => (
            <li key={o.overlay_id}>
              <button type="button" onClick={() => onSelect(o)} aria-label={`${s.timeline.replay}: ${o.title ?? s.kicker[o.type]}, ${o.show_at}`}>
                <span className="moments-time">{o.show_at}</span>
                <span className={`moments-kind kind-${o.type}`}>{s.kicker[o.type]}</span>
                <span className="moments-title">{o.title}</span>
                {mode === 'analyst' && o.type === 'duel_bar' && <span className="mono">{signed(o.data.bar, lang)}</span>}
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState>{s.timeline.empty}</EmptyState>
      )}
    </section>
  );
}
