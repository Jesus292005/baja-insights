import { useLayoutEffect, useRef, useState } from 'react';
import type { OverlayOrder, Slot } from '../../contracts/overlay';
import { usePrefs } from '../../i18n/prefs';
import { isFrame } from '../../logic/derive';
import { SLOTS, type Showing } from '../../logic/plan';
import { Graphic, GraphicLayoutContext } from './graphics';

/**
 * The broadcast graphics, shown off the pitch in the web app. They are drawn in canvas pixels
 * (TV scale), so each one is laid out at a canvas width and scaled down to web size, in the wide
 * 'band' layout (see graphics.tsx).
 */

/** Web size of the canvas text: a 44 px title reads at about 24 px. */
const MAX_SCALE = 0.55;
/** Narrowest canvas width a card is laid out at; below it the card scales down instead. */
const MIN_WIDTH = 480;
/** From this canvas width on, the card puts its data beside the title instead of below it. */
const WIDE = 900;

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
  /** No countdown line: the card stays until the viewer closes it. */
  still?: boolean;
}

/**
 * One graphic at web size, as wide as its box: it is laid out at the canvas width that fills the
 * box at web scale, so every card has the same width and no empty space beside it.
 */
export function ScaledGraphic({ order, elapsed, orders, still }: ScaledGraphicProps) {
  const { ref, width: room } = useWidth<HTMLDivElement>();
  const inner = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const width = Math.max(MIN_WIDTH, room / MAX_SCALE);
  const scale = room > 0 ? room / width : 0;

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
      ref={ref}
      className={`card-scale${still ? ' is-still' : ''}${width >= WIDE ? ' is-wide' : ''}`}
      style={{ height: height * scale, visibility: scale && height ? 'visible' : 'hidden' }}
    >
      <div ref={inner} className="card-scale-inner" style={{ width, transform: `scale(${scale})` }}>
        <GraphicLayoutContext.Provider value="band">
          <Graphic order={order} elapsed={elapsed} orders={orders} />
        </GraphicLayoutContext.Provider>
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
  const items = bandItems(showing);
  return (
    <section className={`card-band${items.length ? '' : ' is-empty'}`} aria-label={s.band.label}>
      {items.length ? (
        items.map((item) => (
          <ScaledGraphic key={item.order.overlay_id} order={item.order} elapsed={item.elapsed} orders={orders} />
        ))
      ) : (
        <p className="card-band-empty">{s.band.empty}</p>
      )}
    </section>
  );
}
