import { useEffect, useState } from 'react';
import { positionsUrl } from 'virtual:match-data';
import type { PositionsFile } from '../logic/positions';

/**
 * The illustrative positions, fetched once and shared by every view. The file is 3 MB, so it is
 * not part of the bundle: the pitch draws the play alone until it arrives, or if it never does.
 */
let request: Promise<PositionsFile | null> | null = null;

/** True when the match has a positions file to draw. */
export const hasPositions = positionsUrl !== null;

function load(): Promise<PositionsFile | null> {
  if (!positionsUrl) return Promise.resolve(null);
  request ??= fetch(positionsUrl)
    .then((r) => (r.ok ? (r.json() as Promise<PositionsFile>) : null))
    .catch(() => null);
  return request;
}

/**
 * Hands the dead-ball spells of the set pieces to the replay, which passes them quickly in skip
 * mode (ReplaySource.setDeadBall).
 */
export function useDeadBall(replay: { setDeadBall(spells: { from: number; to: number }[]): void } | null, file: PositionsFile | null) {
  useEffect(() => {
    replay?.setDeadBall(file ? file.set_pieces.map((p) => ({ from: p.ball_out_from_t_s, to: p.t_s })) : []);
  }, [replay, file]);
}

export function usePositions(enabled = true): PositionsFile | null {
  const [file, setFile] = useState<PositionsFile | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    load().then((f) => {
      if (live) setFile(f);
    });
    return () => {
      live = false;
    };
  }, [enabled]);
  return enabled ? file : null;
}
