import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { OverlayOrder, Slot } from '../../contracts/overlay';
import { broadcastSlots } from '../../design/tokens';
import { usePrefs } from '../../i18n/prefs';
import { SLOTS, type Showing } from '../../logic/plan';
import { Graphic } from './graphics';

export interface StageProps {
  showing: Partial<Record<Slot, Showing>>;
  orders: readonly OverlayOrder[];
  variant: 'web' | 'broadcast';
  /** Web only: a moment replayed from the timeline, shown in its own slot. */
  override?: Showing | null;
  /** Broadcast only: a slot-sized placeholder for the score bug. */
  bug?: React.ReactNode;
}

const { width: W, height: H } = broadcastSlots.canvas;

/** Fits the 1920×1080 canvas into its box. */
function useFitScale(fit: 'width' | 'contain') {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      setScale(fit === 'width' ? r.width / W : Math.min(r.width / W, r.height / H));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit]);
  return { ref, scale };
}

/** Reads each new graphic aloud once, at most one every 5 s, never the duel frames. */
function useAnnouncer(showing: Partial<Record<Slot, Showing>>, enabled: boolean) {
  const [message, setMessage] = useState('');
  const seen = useRef(new Set<string>());
  const lastAt = useRef(0);
  const pending = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    for (const slot of SLOTS) {
      const o = showing[slot]?.order;
      if (!o || seen.current.has(o.overlay_id) || o.source_insight === null) continue;
      seen.current.add(o.overlay_id);
      pending.current = [o.title, o.text].filter(Boolean).join('. ');
    }
    const now = Date.now();
    if (pending.current && now - lastAt.current > 5000) {
      setMessage(pending.current);
      pending.current = null;
      lastAt.current = now;
    }
  }, [showing, enabled]);
  return message;
}

export function Stage({ showing, orders, variant, override, bug }: StageProps) {
  const { s } = usePrefs();
  const { ref, scale } = useFitScale(variant === 'web' ? 'width' : 'contain');
  const merged: Partial<Record<Slot, Showing>> = { ...showing };
  if (override) merged[override.order.slot] = override;
  const announcement = useAnnouncer(merged, variant === 'web');

  return (
    <div ref={ref} className={`stage stage-${variant}`}>
      <div
        className="stage-canvas"
        style={{
          width: W,
          height: H,
          transform: variant === 'broadcast' ? `translate(-50%, -50%) scale(${scale})` : `scale(${scale})`,
          visibility: scale ? 'visible' : 'hidden',
        }}
      >
        {variant === 'web' && <PitchBackdrop label={s.app.videoPlaceholder} />}
        {bug}
        {SLOTS.map((slot) => {
          const item = merged[slot];
          const box = broadcastSlots[slot];
          return (
            <div
              key={slot}
              className={`slot slot-${slot}`}
              style={{ left: box.x, top: box.y, width: box.w, ...(slot === 'full_screen' ? { height: box.h } : { maxHeight: box.h }) }}
            >
              {item && <Graphic key={item.order.overlay_id} order={item.order} elapsed={item.elapsed} orders={orders} />}
            </div>
          );
        })}
      </div>
      {variant === 'web' && (
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {announcement}
        </div>
      )}
    </div>
  );
}

/** Stand-in for the video feed in the web app: a quiet pitch so the graphics have context. */
function PitchBackdrop({ label }: { label: string }) {
  return (
    <div className="pitch" aria-hidden="true">
      <svg viewBox="0 0 1050 680" preserveAspectRatio="xMidYMid slice">
        <defs>
          <pattern id="mow" width="105" height="680" patternUnits="userSpaceOnUse">
            <rect width="52.5" height="680" fill="var(--pitch-a)" />
            <rect x="52.5" width="52.5" height="680" fill="var(--pitch-b)" />
          </pattern>
        </defs>
        <rect width="1050" height="680" fill="url(#mow)" />
        <g fill="none" stroke="var(--pitch-line)" strokeWidth="3">
          <rect x="20" y="20" width="1010" height="640" />
          <line x1="525" y1="20" x2="525" y2="660" />
          <circle cx="525" cy="340" r="91.5" />
          <rect x="20" y="138.5" width="165" height="403" />
          <rect x="865" y="138.5" width="165" height="403" />
          <rect x="20" y="248.5" width="55" height="183" />
          <rect x="975" y="248.5" width="55" height="183" />
          <circle cx="130" cy="340" r="3" fill="var(--pitch-line)" />
          <circle cx="920" cy="340" r="3" fill="var(--pitch-line)" />
        </g>
      </svg>
      <span className="pitch-label">{label}</span>
    </div>
  );
}
