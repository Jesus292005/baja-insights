import { useEffect, useRef, useState } from 'react';
import { roster } from '../../data/match';
import { usePrefs } from '../../i18n/prefs';
import type { Scoreline } from '../../contracts/overlay';
import { SECOND_HALF_S } from '../../logic/play';
import type { Phase } from '../../stream/types';
import { TeamChip } from '../common';

/** How long the notice stays after the clock crosses 45:00, in real seconds. */
const SHOW_MS = 6000;
/** A bigger step than this (match seconds) is a seek, not the match playing through half time. */
const MAX_STEP_S = 120;

/**
 * True while the half-time notice is on: during the live half-time pause, and for a few seconds
 * after the clock crosses 45:00 while playing (the replay has no pause: half_time and
 * second_half_start share second 2700).
 */
export function useHalfTime(t: number, phase: Phase | undefined) {
  const prev = useRef(t);
  const [crossedAt, setCrossedAt] = useState<number | null>(null);
  useEffect(() => {
    const before = prev.current;
    prev.current = t;
    if (before < SECOND_HALF_S && t >= SECOND_HALF_S && t - before <= MAX_STEP_S) setCrossedAt(Date.now());
    // Going back before 45:00 hides it, so it can show again on the next crossing.
    if (t < SECOND_HALF_S) setCrossedAt(null);
  }, [t]);
  useEffect(() => {
    if (crossedAt === null) return;
    const id = setTimeout(() => setCrossedAt(null), SHOW_MS);
    return () => clearTimeout(id);
  }, [crossedAt]);
  return phase === 'half_time' || crossedAt !== null;
}

/**
 * Notice on the pitch at half time (canvas pixels): the score, and that the teams swap ends.
 * In the second half Bahía FC attacks to the left and Real Cardón to the right (see logic/play.ts).
 */
export function HalfTimeNotice({ scoreline }: { scoreline: Scoreline | null }) {
  const { s } = usePrefs();
  return (
    <section className="halftime" role="status" aria-label={s.halftime.title}>
      <p className="halftime-kicker">{s.halftime.title}</p>
      {scoreline && (
        <p className="halftime-score">
          <TeamChip team={roster.home} /> {scoreline.home} – {scoreline.away} <TeamChip team={roster.away} />
        </p>
      )}
      <p className="halftime-swap">{s.halftime.swap}</p>
      <p className="halftime-ends">
        <span><span aria-hidden="true">←</span> <TeamChip team={roster.home} /> {roster.home.name}</span>
        <span>{roster.away.name} <TeamChip team={roster.away} /> <span aria-hidden="true">→</span></span>
      </p>
      <p className="halftime-note">{s.halftime.attacks}</p>
    </section>
  );
}
