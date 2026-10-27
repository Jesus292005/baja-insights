import { useEffect, useRef, useState } from 'react';
import { frameAt, lineupAt, type PositionsFile } from '../../logic/positions';
import { GlideClock } from '../../logic/glide';
import { inHalf, toSvg, type Half } from '../../logic/play';

/**
 * The 22 players and the ball, drawn under the play (pitch SVG units). Illustrative: placed by a
 * model anchored to the events, see logic/positions.ts.
 *
 * The match clock moves in steps (every 100 ms, 6 match seconds at 60×), so the layer draws from
 * a GlideClock that moves on every frame and never jumps on a step (logic/glide.ts).
 */

/** The match second to draw on each frame. `hold` (paused, or a frozen moment) draws `target` as it is. */
function useGlide(target: number, hold: boolean) {
  const clock = useRef(new GlideClock()).current;
  const [shown, setShown] = useState(target);

  useEffect(() => {
    const now = performance.now();
    clock.update(target, now, hold);
    setShown(clock.value(now));
  }, [clock, target, hold]);

  useEffect(() => {
    if (hold) return;
    let id = requestAnimationFrame(function loop() {
      setShown(clock.value(performance.now()));
      id = requestAnimationFrame(loop);
    });
    return () => cancelAnimationFrame(id);
  }, [clock, hold]);

  return hold ? target : shown;
}

export function PlayersLayer({ file, t, half, frozen }: { file: PositionsFile; t: number; half: Half; frozen: boolean }) {
  const shown = useGlide(t, frozen);
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
