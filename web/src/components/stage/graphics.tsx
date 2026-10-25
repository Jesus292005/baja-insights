import type { CSSProperties, ReactNode } from 'react';
import type {
  CardUpgradeOrder, ChatAnswerOrder, DuelBarOrder, GoalAnalysisOrder, HomeAway, MatchKeysOrder, MvpUpdateOrder,
  OverlayOrder, StandoutMilestoneOrder, TeamPhaseOrder, Top3Order,
} from '../../contracts/overlay';
import { invisibleAssistPlayer } from '../../contracts/overlay';
import { roster } from '../../data/match';
import type { TeamRef } from '../../data/roster';
import { usePrefs } from '../../i18n/prefs';
import {
  asSent, attributeLabel, attributeShort, clock, ordinal, pct, positionLabel, signedPct, surname, t,
} from '../../i18n/strings';
import { cardAt } from '../../logic/derive';
import { Evidence, TeamChip } from '../common';
import { DuelMeter } from '../DuelMeter';
import { PlayerCard } from '../PlayerCard';

/**
 * One graphic per order type, drawn on the 1920×1080 canvas. Title and text come from the
 * order exactly as the agents wrote them; numbers come from `data` and `card`.
 */

export interface GraphicProps<O extends OverlayOrder = OverlayOrder> {
  order: O;
  elapsed: number;
  /** All orders the viewer received, for cards that need the match so far. */
  orders: readonly OverlayOrder[];
}

/* ---------- Frame ---------- */

function Panel({
  order, elapsed, team, children, className = '',
}: {
  order: OverlayOrder; elapsed: number; team?: TeamRef; children?: ReactNode; className?: string;
}) {
  const { s } = usePrefs();
  const text = order.text && <p className="g-text">{order.text}</p>;
  return (
    <section className={`g-panel g-${order.type} ${className}`} aria-label={order.title ?? s.kicker[order.type]}>
      <header className="g-kicker">
        <span className="g-dot" aria-hidden="true" />
        <span>{s.kicker[order.type]}</span>
        <TeamChip team={team} />
        <span className="g-kicker-time">{order.show_at}</span>
      </header>
      {order.title && <h2 className="g-title">{order.title}</h2>}
      {children}
      {text}
      <Tide duration={order.duration_s} elapsed={elapsed} />
    </section>
  );
}

/** Tide line: empties while the graphic is on screen. A counter replaces it with reduced motion. */
function Tide({ duration, elapsed }: { duration: number; elapsed: number }) {
  const remaining = Math.max(0, 1 - elapsed / duration);
  const left = Math.max(0, Math.ceil(duration - elapsed));
  return (
    <div className="g-tide" aria-hidden="true">
      <i style={{ transform: `scaleX(${remaining})` }} />
      <span className="g-tide-count">{left} s</span>
    </div>
  );
}

const teamOf = (player: string | undefined) => roster.player(player)?.team;

/* ---------- 1. MVP ---------- */

function MvpUpdate({ order, elapsed }: GraphicProps<MvpUpdateOrder>) {
  const { s, lang, mode } = usePrefs();
  const { rank, previous_rank, mvp_score } = order.data;
  const card = order.card;
  return (
    <Panel order={order} elapsed={elapsed} team={teamOf(card?.player)}>
      <div className="g-rank">
        <span className="g-rank-big">{ordinal(rank, lang)}</span>
        {previous_rank !== undefined && previous_rank > rank && (
          <span className="g-up">▲ {t(s.mvp.rankUp, { from: ordinal(previous_rank, lang), to: ordinal(rank, lang) })}</span>
        )}
        {mode === 'analyst' && (
          <span className="g-score">{s.mvp.score} <b>{asSent(mvp_score, lang)}</b></span>
        )}
      </div>
      {card && (
        <p className="g-card-change">
          <abbr title={attributeLabel[lang][card.attribute]}>{attributeShort[lang][card.attribute]}</abbr> {card.from} → <b>{card.to}</b>{' '}
          <span className="g-up">+{card.delta}</span>
        </p>
      )}
      {mode === 'analyst' && <Evidence ids={order.evidence} />}
    </Panel>
  );
}

/* ---------- 2. Duel ---------- */

/** Bottom bar: one caption line (kicker + agent text, title as accessible name) over the meter. */
function DuelBar({ order, elapsed }: GraphicProps<DuelBarOrder>) {
  const { s } = usePrefs();
  const frame = order.source_insight === null;
  const label = order.title ?? `${order.data.player_a} – ${order.data.player_b}`;
  return (
    <section className={`g-panel g-duel_bar${frame ? ' g-frame' : ''}`} aria-label={label}>
      {!frame && (order.text || order.title) && (
        <p className="g-duel-caption">
          <span className="g-duel-kicker"><span className="g-dot" aria-hidden="true" />{s.kicker.duel_bar}</span>
          {order.text ?? order.title}
        </p>
      )}
      <DuelMeter playerA={order.data.player_a} playerB={order.data.player_b} bar={order.data.bar} size="broadcast" />
      {!frame && <Tide duration={order.duration_s} elapsed={elapsed} />}
    </section>
  );
}

/* ---------- 3. Milestone ---------- */

function Standout({ order, elapsed, orders }: GraphicProps<StandoutMilestoneOrder>) {
  const { s, lang, mode } = usePrefs();
  const name = order.card?.player;
  const card = name ? cardAt(roster, orders, name, order.show_at_s) : null;
  const d = order.data ?? {};
  const rows: [string, ReactNode][] = [];
  if (d.recoveries !== undefined) rows.push([s.stats.recoveries, d.recoveries]);
  if (d.duels_won !== undefined) rows.push([s.stats.duels, d.duels_total ? `${d.duels_won} / ${d.duels_total}` : d.duels_won]);
  if (d.progressive_passes !== undefined) rows.push([s.stats.progressive_passes, d.progressive_passes]);
  if (d.key_passes !== undefined) rows.push([s.stats.key_passes, d.key_passes]);
  if (d.vs_role !== undefined) rows.push([s.stats.vs_role, signedPct(d.vs_role, lang)]);
  if (d.mvp_rank !== undefined) rows.push([s.stats.mvp_rank, ordinal(d.mvp_rank, lang)]);
  return (
    <Panel order={order} elapsed={elapsed} team={card?.player.team}>
      <div className="g-standout">
        {card && (
          <PlayerCard
            player={card.player}
            attributes={card.attributes}
            overall={card.overall}
            changed={new Set(card.changes.map((c) => c.attribute))}
            highlight={order.card?.attribute}
            size="sm"
          />
        )}
        {mode === 'analyst' && rows.length > 0 && (
          <dl className="g-stats">
            {rows.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
        )}
      </div>
      {mode === 'analyst' && <Evidence ids={order.evidence} />}
    </Panel>
  );
}

/* ---------- 5. Card ---------- */

function CardUpgrade({ order, elapsed }: GraphicProps<CardUpgradeOrder>) {
  const { s, lang, mode } = usePrefs();
  const c = order.card;
  const player = roster.player(c.player);
  return (
    <Panel order={order} elapsed={elapsed} team={player?.team} className="g-card-upgrade">
      <div className="g-upgrade">
        <div className="g-upgrade-attr">
          <abbr title={attributeLabel[lang][c.attribute]}>{attributeShort[lang][c.attribute]}</abbr>
          <span className="g-upgrade-to">{c.to}</span>
          <span className="g-upgrade-from">{c.from} → <span className="g-up">+{c.delta}</span></span>
        </div>
        <div className="g-upgrade-who">
          <b>{c.player}</b>
          <span>{positionLabel[lang][c.position].long}</span>
          {c.overall_to !== undefined && <span>{s.card.overall} {c.overall_to}</span>}
          {mode === 'analyst' && c.reason && <span className="g-reason">{c.reason}</span>}
        </div>
      </div>
    </Panel>
  );
}

/* ---------- 4. Goal chain ---------- */

function GoalChain({ order, elapsed }: GraphicProps<GoalAnalysisOrder>) {
  const { s, lang, mode } = usePrefs();
  const d = order.data;
  const invisible = invisibleAssistPlayer(d.invisible_assist);
  const detail = d.chain_detail;
  const space = typeof d.invisible_assist === 'object' && d.invisible_assist ? d.invisible_assist.space_opened_m : null;
  const scorer = d.chain[d.chain.length - 1];
  return (
    <Panel order={order} elapsed={elapsed} team={teamOf(scorer)}>
      {d.scoreline && (
        <p className="g-scoreline">
          <TeamChip team={roster.home} /> {d.scoreline.home} – {d.scoreline.away} <TeamChip team={roster.away} />
        </p>
      )}
      <ol className="g-chain" style={{ '--n': d.chain.length } as CSSProperties}>
        {d.chain.map((name, i) => {
          const isInvisible = name === invisible;
          const isScorer = i === d.chain.length - 1;
          return (
            <li key={`${name}-${i}`} className={`${isInvisible ? 'is-invisible' : ''}${isScorer ? ' is-scorer' : ''}`} style={{ animationDelay: `${i * 150}ms` }}>
              <span className="g-node" aria-hidden="true">{surname(name).slice(0, 2).toUpperCase()}</span>
              <b>{name}</b>
              {mode === 'analyst' && detail?.[i] && <small>{detail[i].action} · {clock(detail[i].t_s)}</small>}
              {mode === 'analyst' && d.credit[i] !== undefined && (
                <span className="g-credit">
                  <span className="g-credit-bar" style={{ width: `${d.credit[i] * 100}%` }} />
                  <span className="mono">{pct(d.credit[i], lang)}%</span>
                </span>
              )}
            </li>
          );
        })}
      </ol>
      {invisible && (
        <p className="g-invisible">
          <span className="g-invisible-badge">{s.goal.invisible}</span> {invisible}
          <span className="g-invisible-hint">
            {s.goal.invisibleHint}
            {space !== null && ` ${t(s.goal.spaceOpened, { meters: asSent(space, lang) })}.`}
          </span>
        </p>
      )}
      {mode === 'analyst' && (
        <div className="g-row">
          {d.xg !== undefined && <span className="g-score">xG <b>{asSent(d.xg, lang)}</b></span>}
          <Evidence ids={order.evidence ?? detail?.map((l) => l.event_id)} />
        </div>
      )}
    </Panel>
  );
}

/* ---------- Team phase and match keys ---------- */

function Metric({ label, value, unit = '' }: { label: string; value: number | HomeAway | undefined; unit?: string }) {
  const { lang } = usePrefs();
  if (value === undefined) return null;
  if (typeof value === 'number') {
    return <div className="g-metric"><dt>{label}</dt><dd>{asSent(value, lang)}{unit}</dd></div>;
  }
  return (
    <div className="g-metric">
      <dt>{label}</dt>
      <dd>
        <TeamChip team={roster.home} /> {asSent(value.home, lang)}{unit}
        <span className="g-metric-sep" aria-hidden="true">·</span>
        <TeamChip team={roster.away} /> {asSent(value.away, lang)}{unit}
      </dd>
    </div>
  );
}

function TeamPhase({ order, elapsed }: GraphicProps<TeamPhaseOrder>) {
  const { s, mode } = usePrefs();
  const d = order.data;
  return (
    <Panel order={order} elapsed={elapsed}>
      {d && <p className={`g-phase g-phase-${d.label}`}>{s.phase[d.label]}</p>}
      {d && mode === 'analyst' && (
        <dl className="g-stats">
          <Metric label={s.stats.possession} value={d.possession_pct} unit="%" />
          <Metric label={s.stats.pass_accuracy} value={d.pass_accuracy_pct} unit="%" />
          <Metric label={s.stats.passes_per_min} value={d.passes_per_min} />
          <Metric label={s.stats.def_height} value={d.def_action_height_m} unit=" m" />
        </dl>
      )}
    </Panel>
  );
}

function MatchKeys({ order, elapsed }: GraphicProps<MatchKeysOrder>) {
  const { s, mode } = usePrefs();
  const d = order.data;
  return (
    <Panel order={order} elapsed={elapsed}>
      {d?.scoreline && (
        <p className="g-scoreline">
          <TeamChip team={roster.home} /> {d.scoreline.home} – {d.scoreline.away} <TeamChip team={roster.away} />
        </p>
      )}
      {d && mode === 'analyst' && (
        <dl className="g-stats">
          <Metric label={s.keys.xg} value={{ home: d.xg.home, away: d.xg.away }} />
          <Metric label={s.keys.possession} value={d.possession_pct} unit="%" />
        </dl>
      )}
      {d && (
        <div className="g-split" aria-hidden="true">
          <span className="g-split-home" style={{ flexGrow: d.possession_pct.home }} />
          <span className="g-split-away" style={{ flexGrow: d.possession_pct.away }} />
        </div>
      )}
      <p className="g-note">{s.keys.noPrediction}</p>
      {mode === 'analyst' && <Evidence ids={order.evidence} />}
    </Panel>
  );
}

/* ---------- Top 3 ---------- */

function Top3({ order, elapsed, orders }: GraphicProps<Top3Order>) {
  const { s, lang } = usePrefs();
  const { cards, final_scoreline } = order.data;
  return (
    <div className="g-fullscreen">
      <Panel order={order} elapsed={elapsed} className="g-top3-panel">
        {final_scoreline && (
          <p className="g-scoreline">
            {s.status.fullTime} · <TeamChip team={roster.home} /> {final_scoreline.home} – {final_scoreline.away} <TeamChip team={roster.away} />
          </p>
        )}
        <ol className="g-podium">
          {cards.map((c) => {
            const card = cardAt(roster, orders, c.player, order.show_at_s);
            return (
              <li key={c.rank} className={`g-podium-${c.rank}`}>
                <span className="g-podium-rank">{ordinal(c.rank, lang)}</span>
                {card ? (
                  <PlayerCard
                    player={card.player}
                    attributes={card.attributes}
                    overall={card.overall}
                    changed={new Set(card.changes.map((x) => x.attribute))}
                    size={c.rank === 1 ? 'lg' : 'md'}
                    footer={`${s.mvp.score} ${asSent(c.mvp_score, lang)}`}
                  />
                ) : (
                  <b>{c.player} · {asSent(c.mvp_score, lang)}</b>
                )}
              </li>
            );
          })}
        </ol>
      </Panel>
    </div>
  );
}

/* ---------- Chat answer ---------- */

function ChatAnswer({ order, elapsed }: GraphicProps<ChatAnswerOrder>) {
  const { s } = usePrefs();
  return (
    <Panel order={order} elapsed={elapsed}>
      {order.data && <p className="g-question">“{order.data.question}”</p>}
      {order.data?.tools.length ? (
        <div className="evidence">
          <span className="evidence-label">{s.chat.answeredWith}</span>
          {order.data.tools.map((x) => <code key={x} className="evidence-chip">{x}</code>)}
        </div>
      ) : null}
    </Panel>
  );
}

/* ---------- Dispatcher ---------- */

export function Graphic(props: GraphicProps) {
  const { order } = props;
  switch (order.type) {
    case 'mvp_update': return <MvpUpdate {...props} order={order} />;
    case 'duel_bar': return <DuelBar {...props} order={order} />;
    case 'standout_milestone': return <Standout {...props} order={order} />;
    case 'card_upgrade': return <CardUpgrade {...props} order={order} />;
    case 'goal_analysis': return <GoalChain {...props} order={order} />;
    case 'team_phase': return <TeamPhase {...props} order={order} />;
    case 'match_keys': return <MatchKeys {...props} order={order} />;
    case 'top3': return <Top3 {...props} order={order} />;
    case 'chat_answer': return <ChatAnswer {...props} order={order} />;
    default: return null;
  }
}
