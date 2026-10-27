import { useEffect } from 'react';
import type { OverlayOrder } from '../../contracts/overlay';
import { roster } from '../../data/match';
import { usePrefs } from '../../i18n/prefs';
import { t as fill } from '../../i18n/strings';
import { cardAt } from '../../logic/derive';
import { PlayerCard } from '../PlayerCard';

/**
 * The card of a player picked on the pitch, in its top-right corner. Small, so the play stays in
 * view, at the second the pitch shows. Closed by its button, by Escape or by a click on the pitch.
 */
export function PlayerCorner({ player, orders, t, onClose }: { player: string; orders: readonly OverlayOrder[]; t: number; onClose: () => void }) {
  const { s } = usePrefs();
  const card = cardAt(roster, orders, player, t);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!card) return null;
  return (
    // A click inside the card is not a click on the pitch.
    <aside className="player-corner" aria-label={fill(s.players.cardOf, { player })} onClick={(e) => e.stopPropagation()}>
      <button type="button" className="player-corner-close" onClick={onClose} aria-label={s.players.close} title={s.players.close}>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <PlayerCard
        player={card.player}
        attributes={card.attributes}
        overall={card.overall}
        overallFrom={card.overallFrom}
        changed={new Set(card.changes.map((c) => c.attribute))}
        size="sm"
      />
    </aside>
  );
}
