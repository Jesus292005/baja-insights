import { useEffect, useRef, useState } from 'react';
import { frameAt, lineupAt, type PositionsFile } from '../../logic/positions';
import { inHalf, toSvg, type Half } from '../../logic/play';

/**
 * The 22 players and the ball, drawn under the play (pitch SVG units). Illustrative: placed by a
 * model anchored to the events, see logic/positions.ts.
 *
 * The match clock moves in steps (every 100 ms, 6 match seconds at 60×), so the layer keeps its own
 * clock between steps at the pace the match is going, and the players glide instead of jumping.
 */

/** A bigger step than this (match seconds) is a seek: jump there instead of gliding. */
const SEEK_S = 20;

function useSmoothClock(target: number, frozen: boolean) {
  const last = useRef({ t: target, at: performance.now(), rate: 0 });
  const [shown, setShown] = useState(target);

  // Each new clock value: how fast the match is going, from the step since the last one.
  useEffect(() => {
    const now = performance.now();
    const prev = last.current;
    const dt = (now - prev.at) / 1000;
    const jump = Math.abs(target - prev.t) > SEEK_S || target < prev.t;
    const rate = frozen || jump || dt <= 0 ? 0 : Math.min(240, (target - prev.t) / dt);
    last.current = { t: target, at: now, rate };
    setShown(target);
  }, [target, frozen]);

  // Between values, carry on at that pace, never more than one step ahead.
  useEffect(() => {
    if (frozen) return;
    let id = requestAnimationFrame(function loop() {
      const { t, at, rate } = last.current;
      if (rate > 0) setShown(t + rate * Math.min((performance.now() - at) / 1000, 0.15));
      id = requestAnimationFrame(loop);
    });
    return () => cancelAnimationFrame(id);
  }, [frozen]);

  return frozen ? target : shown;
}

export function PlayersLayer({ file, t, half, frozen }: { file: PositionsFile; t: number; half: Half; frozen: boolean }) {
  const shown = useSmoothClock(t, frozen);
  const frame = frameAt(file, shown);
  if (!frame) return null;
  const lineup = lineupAt(file, shown);
  const at = (p: [number, number]) => toSvg(inHalf(p, half));
  const [bx, by] = at(frame.ball);
  return (
    <g className="pp" aria-hidden="true">
      {(['home', 'away'] as const).map((side) =>
        frame[side].map((p, slot) => {
          const [x, y] = at(p);
          const who = lineup[side][slot];
          return (
            <g key={`${side}-${slot}`} className={`pp-player pp-${side}${slot === 0 ? ' pp-keeper' : ''}`} transform={`translate(${x} ${y})`}>
              <title>{who ? `${who.number} ${who.player}` : ''}</title>
              <circle r="18" />
              <text y="6.5" textAnchor="middle">{who?.number}</text>
            </g>
          );
        }),
      )}
      <circle className="pp-ball" cx={bx} cy={by} r="8" />
    </g>
  );
}
