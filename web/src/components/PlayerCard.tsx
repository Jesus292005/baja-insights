import type { CardAttribute } from '../contracts/overlay';
import { CARD_ATTRIBUTES, type PlayerRef } from '../data/roster';
import { cardTier } from '../design/tokens';
import { usePrefs } from '../i18n/prefs';
import { attributeLabel, attributeShort, positionLabel, t } from '../i18n/strings';

export interface PlayerCardProps {
  player: PlayerRef;
  attributes: Record<CardAttribute, number>;
  /** Engine overall; null shows "Overall not available" instead of computing one. */
  overall: number | null;
  /** Overall before the latest change, when the engine says it moved. Shows ▲ and the old value. */
  overallFrom?: number | null;
  /** Attributes that went up during the match. */
  changed?: ReadonlySet<CardAttribute>;
  /** Attribute that just went up, animated once. */
  highlight?: CardAttribute;
  size: 'sm' | 'md' | 'lg';
  /** Extra line under the name, e.g. the MVP score in the top 3. */
  footer?: string;
}

export function PlayerCard({ player, attributes, overall, overallFrom, changed, highlight, size, footer }: PlayerCardProps) {
  const { s, lang } = usePrefs();
  // The tier is a presentation threshold on the overall the engine (or teams.json) sent.
  const tier = cardTier(overall ?? player.overall);
  const pos = positionLabel[lang][player.position];
  return (
    <article
      className={`pcard pcard-${size} tier-${tier}`}
      aria-label={`${player.name}, ${pos.long}, ${player.team.name}. ${s.card.tier[tier]}. ${s.card.overall} ${overall ?? s.card.overallPending}`}
    >
      <div className="pcard-tier">
        <span>{s.card.tier[tier]}</span>
        <span>{player.team.short} #{player.number}</span>
      </div>
      <div className="pcard-top">
        {overall !== null ? (
          <span className={`pcard-ovr${overallFrom != null ? ' is-up' : ''}`}>{overall}</span>
        ) : (
          <span className="pcard-ovr pcard-ovr-none" title={s.card.overallPending}>—</span>
        )}
        <span className="pcard-pos">
          <abbr title={pos.long}>{pos.short}</abbr>
          <small>
            {overall === null ? s.card.overallPending : overallFrom != null ? `▲ ${t(s.card.overallUp, { from: overallFrom })}` : s.card.overall}
          </small>
        </span>
      </div>
      <div className="pcard-name">{player.name}</div>
      {footer && <div className="pcard-footer">{footer}</div>}
      <ul className="pcard-attrs">
        {CARD_ATTRIBUTES.map((a) => (
          <li key={a} className={`${changed?.has(a) ? 'is-up' : ''}${highlight === a ? ' is-highlight' : ''}`}>
            <abbr title={attributeLabel[lang][a]}>{attributeShort[lang][a]}</abbr>
            <b>{attributes[a]}</b>
          </li>
        ))}
      </ul>
    </article>
  );
}
