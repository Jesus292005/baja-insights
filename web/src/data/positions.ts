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
