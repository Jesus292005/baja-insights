import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { OverlayOrder, Slot } from '../../contracts/overlay';
import { broadcastSlots } from '../../design/tokens';
import { usePrefs } from '../../i18n/prefs';
import { t } from '../../i18n/strings';
import { isFrame } from '../../logic/derive';
import { SLOTS, type Showing } from '../../logic/plan';
import { placeCards, playPoints, type Box, type CardToPlace } from '../../logic/dodge';
import { VIEW_BOX, defendsLeft, type Half, type MatchPlay } from '../../logic/play';
import { roster } from '../../data/match';
import { PlayLayer } from './PlayLayer';
import { PlayersLayer } from './PlayersLayer';
import type { PositionsFile } from '../../logic/positions';
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
  /** The 22 players and the ball at second t (needs the backdrop). Frozen: no gliding, for a moment opened from the list. */
  players?: { file: PositionsFile; t: number; frozen: boolean; onSelect?: (player: string) => void; selected?: string | null } | null;
  /** Extra layers on the canvas, in canvas pixels (cinema badge and help). */
  children?: React.ReactNode;
  /** Canvas boxes the cards must leave free when they move off the play (the cinema badge). */
  reserved?: readonly Box[];
  /** Web app: a click on the pitch outside a player (closes the player card). */
  onPitchClick?: () => void;
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

export function Stage({ showing, orders, variant, graphics = true, bug, backdrop, play, half, players, children, reserved, onPitchClick }: StageProps) {
  const { s, mode } = usePrefs();
  const { ref, scale } = useFitScale(variant === 'web' ? 'width' : 'contain');
  const announcement = useAnnouncer(showing, variant === 'web');
  const drawnHalf = play?.half ?? half ?? 1;
  // Cinema draws the play behind the cards, so they move to where they cover the least of it.
  const dodge = variant === 'broadcast' && !!backdrop && !!play;
  const boxes = useCardBoxes(showing, drawnHalf, dodge ? play : null, reserved);

  return (
    <div ref={ref} className={`stage stage-${variant}`} onClick={onPitchClick}>
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
          <PitchBackdrop
            label={players ? s.players.illustrative : s.app.videoPlaceholder}
            play={play ?? null}
            half={drawnHalf}
            ends={s.pitch.ends}
            players={players ?? null}
          />
        )}
        {bug}
        {graphics && SLOTS.map((slot) => {
          const item = showing[slot];
          const box = boxes.get(slot)!;
          return (
            <div
              key={slot}
              ref={(el) => {
                boxes.refs[slot] = el;
              }}
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

/** Default place of each slot's graphic: its slot, or for a goal card, the goal dock. */
function homeBox(slot: Slot, item: Showing | undefined, half: Half) {
  return item && slot === 'center' && item.order.type === 'goal_analysis' ? goalDock(item.order, half) : broadcastSlots[slot];
}

/** Score bug of the cinema canvas (slot-bug), which no card may cover. */
const BUG_BOX: Box = { x: 96, y: 54, w: 520, h: 100 };
/** The full screen covers everything anyway: it stays put. */
const FIXED = new Set<Slot>(['full_screen']);
/** The bottom bar spans the canvas: it either stays at the foot or moves up, right of the score bug. */
const BAR_TOP_X = BUG_BOX.x + BUG_BOX.w + 24;
/** Extra height the bar may take up there, being narrower (its caption can wrap to a second line). */
const BAR_TOP_EXTRA = 40;
/** Or full width just below the score bug, the cinema hint and the mode badge. */
const BAR_BELOW_Y = 190;

/**
 * Where each slot's graphic goes. Without a play to dodge, its default place. With one (cinema),
 * each card is measured once rendered and moved to the spot that covers the least of the play;
 * that spot is kept while the card is on screen, so a card never jumps once it is up.
 */
function useCardBoxes(showing: Partial<Record<Slot, Showing>>, half: Half, play: MatchPlay | null, reserved: readonly Box[] = []) {
  const refs = useRef<Partial<Record<Slot, HTMLDivElement | null>>>({}).current;
  const [heights, setHeights] = useState<Record<string, number>>({});
  const kept = useRef(new Map<string, { x: number; y: number; w: number }>()).current;

  // Measure the cards before the browser paints, so a moved card never shows in its old place.
  useLayoutEffect(() => {
    if (!play) return;
    const next: Record<string, number> = {};
    let changed = false;
    for (const slot of SLOTS) {
      const item = showing[slot];
      const el = refs[slot];
      if (!item || !el || FIXED.has(slot)) continue;
      next[item.order.overlay_id] = el.offsetHeight;
      if (heights[item.order.overlay_id] !== el.offsetHeight) changed = true;
    }
    if (changed || Object.keys(next).length !== Object.keys(heights).length) setHeights(next);
  });

  const placed = new Map<Slot, { x: number; y: number; w: number; h: number }>();
  for (const slot of SLOTS) placed.set(slot, homeBox(slot, showing[slot], half));
  if (play) {
    const live = new Set(SLOTS.map((sl) => showing[sl]?.order.overlay_id).filter(Boolean));
    for (const id of [...kept.keys()]) if (!live.has(id)) kept.delete(id);
    const taken: Box[] = [BUG_BOX, ...reserved];
    const fresh: CardToPlace[] = [];
    for (const slot of SLOTS) {
      const item = showing[slot];
      if (!item) continue;
      const home = homeBox(slot, item, half);
      const h = heights[item.order.overlay_id];
      if (FIXED.has(slot)) continue;
      const at = kept.get(item.order.overlay_id);
      if (at && h) {
        placed.set(slot, { ...home, ...at });
        taken.push({ x: at.x, y: at.y, w: at.w, h });
      } else if (h && slot === 'bottom_bar') {
        // At the foot as usual, up top right of the score bug, or full width just below the bug.
        const foot = { x: home.x, y: home.y, w: home.w, h };
        const top = { x: BAR_TOP_X, y: BUG_BOX.y, w: home.x + home.w - BAR_TOP_X, h: h + BAR_TOP_EXTRA };
        const below = { x: home.x, y: BAR_BELOW_Y, w: home.w, h };
        fresh.push({ key: slot, home: foot, only: [foot, top, below] });
      } else if (h) {
        fresh.push({ key: slot, home: { x: home.x, y: home.y, w: home.w, h } });
      }
    }
    if (fresh.length) {
      const chosen = placeCards(fresh, playPoints(play), taken);
      for (const f of fresh) {
        const box = chosen.get(f.key)!;
        const slot = f.key as Slot;
        const home = homeBox(slot, showing[slot], half);
        const at = { x: box.x, y: box.y, w: box.w };
        placed.set(slot, { ...home, ...at });
        kept.set(showing[slot]!.order.overlay_id, at);
      }
    }
  }
  return Object.assign(placed, { refs });
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
function PitchBackdrop({
  label, play, half, ends, players,
}: {
  label: string; play: MatchPlay | null; half: Half; ends: string; players: StageProps['players'];
}) {
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
      <svg viewBox={`${VIEW_BOX.x} ${VIEW_BOX.y} ${VIEW_BOX.w} ${VIEW_BOX.h}`} preserveAspectRatio="xMidYMid meet" role="group" aria-label={t(ends, { left: left.name, right: right.name, half })}>
        <defs>
          <pattern id="mow" x="0" width="105" height="740" patternUnits="userSpaceOnUse">
            <rect width="52.5" height="740" y="-30" fill="var(--pitch-a)" />
            <rect x="52.5" y="-30" width="52.5" height="740" fill="var(--pitch-b)" />
          </pattern>
        </defs>
        <rect x={VIEW_BOX.x} y={VIEW_BOX.y} width={VIEW_BOX.w} height={VIEW_BOX.h} fill="url(#mow)" />
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
        {players && (
          <PlayersLayer file={players.file} t={players.t} half={half} frozen={players.frozen} onSelect={players.onSelect} selected={players.selected} />
        )}
        {play && <PlayLayer key={play.order.overlay_id} play={play} />}
      </svg>
      <span className="pitch-label" aria-hidden="true">{label}</span>
    </div>
  );
}
