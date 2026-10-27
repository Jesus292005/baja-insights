import { useLayoutEffect, useRef, useState } from 'react';
import type { OverlayOrder, Slot } from '../../contracts/overlay';
import { broadcastSlots } from '../../design/tokens';
import { usePrefs } from '../../i18n/prefs';
import { isFrame } from '../../logic/derive';
import { SLOTS, type Showing } from '../../logic/plan';
import { Graphic } from './graphics';

/**
 * The broadcast graphics, shown off the pitch in the web app. They are drawn in canvas pixels
 * (TV scale), so each one is laid out at a canvas width and scaled down to web size.
 */

/** Web size of the canvas text: a 44 px title reads at about 24 px. */
const MAX_SCALE = 0.55;
/** Narrowest canvas width a graphic is laid out at (the right column of the broadcast). */
const MIN_WIDTH = 480;
const MIN_WIDTH_BY_TYPE: Partial<Record<OverlayOrder['type'], number>> = { top3: 1100 };

/** Canvas width for a graphic: its slot's width, narrowed when the room is short. */
function layoutWidth(order: OverlayOrder, room: number) {
  const slot = broadcastSlots[order.slot];
  const min = MIN_WIDTH_BY_TYPE[order.type] ?? MIN_WIDTH;
  const max = order.type === 'top3' ? 1500 : slot.w;
  return Math.max(min, Math.min(max, room / MAX_SCALE));
}

/** Width of an element, kept up to date. */
export function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setWidth(el.getBoundingClientRect().width);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, width };
}

export interface ScaledGraphicProps {
  order: OverlayOrder;
  elapsed: number;
  orders: readonly OverlayOrder[];
  /** Web pixels available for the graphic. */
  room: number;
  /** No countdown line: the card stays until the viewer closes it. */
  still?: boolean;
}

/** One graphic at web size. The box takes the scaled height, so the page flows around it. */
export function ScaledGraphic({ order, elapsed, orders, room, still }: ScaledGraphicProps) {
  const inner = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const width = layoutWidth(order, room);
  const scale = room > 0 ? Math.min(MAX_SCALE, room / width) : 0;

  useLayoutEffect(() => {
    const el = inner.current;
    if (!el) return;
    const measure = () => setHeight(el.offsetHeight);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      className={`card-scale${still ? ' is-still' : ''}`}
      style={{ width: width * scale, height: height * scale, visibility: scale && height ? 'visible' : 'hidden' }}
    >
      <div ref={inner} className="card-scale-inner" style={{ width, transform: `scale(${scale})` }}>
        <Graphic order={order} elapsed={elapsed} orders={orders} />
      </div>
    </div>
  );
}

/** Graphics on screen now, biggest slot first. Duel frames stay out: the duel panel already shows them. */
export function bandItems(showing: Partial<Record<Slot, Showing>>): Showing[] {
  return SLOTS.map((slot) => showing[slot]).filter((x): x is Showing => !!x && !isFrame(x.order));
}

/** Band above the pitch: the cards the planner has on screen, so none of them covers the play. */
export function CardBand({ showing, orders }: { showing: Partial<Record<Slot, Showing>>; orders: readonly OverlayOrder[] }) {
  const { s } = usePrefs();
  const { ref, width } = useWidth<HTMLDivElement>();
  const items = bandItems(showing);
  return (
    <section ref={ref} className={`card-band${items.length ? '' : ' is-empty'}`} aria-label={s.band.label}>
      {items.length ? (
        items.map((item) => (
          <ScaledGraphic key={item.order.overlay_id} order={item.order} elapsed={item.elapsed} orders={orders} room={width} />
        ))
      ) : (
        <p className="card-band-empty">{s.band.empty}</p>
      )}
    </section>
  );
}
