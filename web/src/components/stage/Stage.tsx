import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { OverlayOrder, Slot } from '../../contracts/overlay';
import { broadcastSlots } from '../../design/tokens';
import { usePrefs } from '../../i18n/prefs';
import { t } from '../../i18n/strings';
import { isFrame } from '../../logic/derive';
import { SLOTS, type Showing } from '../../logic/plan';
import { defendsLeft, type Half, type MatchPlay } from '../../logic/play';
import { roster } from '../../data/match';
import { PlayLayer } from './PlayLayer';
import { Graphic } from './graphics';

export interface StageProps {
  showing: Partial<Record<Slot, Showing>>;
  orders: readonly OverlayOrder[];
  variant: 'web' | 'broadcast';
  /** Draws the graphics in their slots. Off in the web app, which shows them in a band above the pitch. */
  graphics?: boolean;
  /** Broadcast only: a slot-sized placeholder for the score bug. */
  bug?: React.ReactNode;
  /** Draws the pitch behind the graphics. Default: only in the web app. */
  backdrop?: boolean;
  /** The play drawn on the pitch (needs the backdrop). */
  play?: MatchPlay | null;
  /** Half the pitch shows when no play is drawn (the play brings its own). Default: first. */
  half?: Half;
  /** Extra layers on the canvas, in canvas pixels (cinema badge and help). */
  children?: React.ReactNode;
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
      if (!o || seen.current.has(o.overlay_id) || isFrame(o)) continue;
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

export function Stage({ showing, orders, variant, graphics = true, bug, backdrop, play, half, children }: StageProps) {
  const { s, mode } = usePrefs();
  const { ref, scale } = useFitScale(variant === 'web' ? 'width' : 'contain');
  const announcement = useAnnouncer(showing, variant === 'web');

  return (
    <div ref={ref} className={`stage stage-${variant}`}>
      <div
        className="stage-canvas"
        data-mode={mode}
        style={{
          width: W,
          height: H,
          transform: variant === 'broadcast' ? `translate(-50%, -50%) scale(${scale})` : `scale(${scale})`,
          visibility: scale ? 'visible' : 'hidden',
        }}
      >
        {(backdrop ?? variant === 'web') && (
          <PitchBackdrop label={s.app.videoPlaceholder} play={play ?? null} half={play?.half ?? half ?? 1} ends={s.pitch.ends} />
        )}
        {bug}
        {graphics && SLOTS.map((slot) => {
          const item = showing[slot];
          const box = item && slot === 'center' && item.order.type === 'goal_analysis' ? goalDock(item.order, play?.half ?? half ?? 1) : broadcastSlots[slot];
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
        {children}
      </div>
      {variant === 'web' && (
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {announcement}
        </div>
      )}
    </div>
  );
}

/**
 * The goal card docks on the side of the pitch the scoring team defends in that half, so the play,
 * which ends at the other goal, stays visible. Teams swap ends at half time (see logic/play.ts).
 */
function goalDock(order: OverlayOrder, half: Half) {
  const scorer = order.type === 'goal_analysis' ? order.data.chain[order.data.chain.length - 1] : undefined;
  const team = roster.player(scorer)?.team.side ?? 'home';
  const dockLeft = defendsLeft(team, half);
  // Below the score bug on the left. The bottom bar is paused during a goal, so the card can reach
  // y = 1000, just above the cinema legend.
  return dockLeft ? { x: 96, y: 140, w: 700, h: 860 } : { x: 1124, y: 54, w: 700, h: 946 };
}

/**
 * Stand-in for the video feed: the whole pitch at true scale (105 × 68 m as 1050 × 680, with a margin),
 * so the plays the engine sends land where they happened. Not drawn in the broadcast overlay, where the
 * real video goes and its camera does not match these coordinates.
 */
function PitchBackdrop({ label, play, half, ends }: { label: string; play: MatchPlay | null; half: Half; ends: string }) {
  // Whose goal is on each end in this half: Bahía defends the left one in the first half.
  const left = defendsLeft('home', half) ? roster.home : roster.away;
  const right = left === roster.home ? roster.away : roster.home;
  const goalColour = (team: typeof left) => `var(--bi-play-${team.side})`;
  const chip = (team: typeof left, cx: number, angle: number) => (
    <g transform={`rotate(${angle} ${cx} 340)`}>
      <rect x={cx - 34} y={326} width={68} height={28} fill={`var(--bi-team-${team.side}-solid)`} />
      <text className="pitch-goal-name" x={cx} y={348} textAnchor="middle">{team.short}</text>
    </g>
  );
  return (
    <div className="pitch" data-half={half}>
      <svg viewBox="-70 -30 1190 740" preserveAspectRatio="xMidYMid meet" role="img" aria-label={t(ends, { left: left.name, right: right.name, half })}>
        <defs>
          <pattern id="mow" x="0" width="105" height="740" patternUnits="userSpaceOnUse">
            <rect width="52.5" height="740" y="-30" fill="var(--pitch-a)" />
            <rect x="52.5" y="-30" width="52.5" height="740" fill="var(--pitch-b)" />
          </pattern>
        </defs>
        <rect x="-70" y="-30" width="1190" height="740" fill="url(#mow)" />
        <g fill="none" stroke="var(--pitch-line)" strokeWidth="3">
          <rect x="0" y="0" width="1050" height="680" />
          <line x1="525" y1="0" x2="525" y2="680" />
          <circle cx="525" cy="340" r="91.5" />
          <rect x="0" y="138.5" width="165" height="403" />
          <rect x="885" y="138.5" width="165" height="403" />
          <rect x="0" y="248.5" width="55" height="183" />
          <rect x="995" y="248.5" width="55" height="183" />
          <rect x="-20" y="303.4" width="20" height="73.2" />
          <rect x="1050" y="303.4" width="20" height="73.2" />
          <circle cx="110" cy="340" r="3" fill="var(--pitch-line)" />
          <circle cx="940" cy="340" r="3" fill="var(--pitch-line)" />
        </g>
        {/* Each goal in the colour of the team that defends it, with its short name beside it. */}
        <g className="pitch-goals">
          <rect x="-20" y="303.4" width="20" height="73.2" fill={goalColour(left)} className="pitch-goal" />
          <rect x="1050" y="303.4" width="20" height="73.2" fill={goalColour(right)} className="pitch-goal" />
          {chip(left, -44, -90)}
          {chip(right, 1094, 90)}
        </g>
        {play && <PlayLayer key={play.order.overlay_id} play={play} />}
      </svg>
      <span className="pitch-label" aria-hidden="true">{label}</span>
    </div>
  );
}
