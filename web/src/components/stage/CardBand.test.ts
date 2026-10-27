import { describe, expect, it } from 'vitest';
import type { OverlayOrder } from '../../contracts/overlay';
import { bandItems } from './CardBand';

const order = (overlay_id: string, type: string, slot: string, source_insight: string | null = 'i1') =>
  ({ overlay_id, type, slot, source_insight }) as unknown as OverlayOrder;

describe('bandItems', () => {
  it('lists the cards on screen, biggest slot first', () => {
    const items = bandItems({
      bottom_bar: { order: order('d', 'duel_bar', 'bottom_bar'), elapsed: 0 },
      top_right: { order: order('m', 'mvp_update', 'top_right'), elapsed: 2 },
      lower_third: { order: order('c', 'card_upgrade', 'lower_third'), elapsed: 1 },
    });
    expect(items.map((x) => x.order.overlay_id)).toEqual(['m', 'c', 'd']);
  });

  it('leaves the duel frames out', () => {
    const items = bandItems({ bottom_bar: { order: order('f', 'duel_bar', 'bottom_bar', null), elapsed: 0 } });
    expect(items).toEqual([]);
  });
});
