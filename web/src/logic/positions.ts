import type { PitchPoint } from '../contracts/overlay';

/**
 * Illustrative positions of the 22 players and the ball (contracts/positions.schema.json).
 * Only for drawing: a deterministic model anchored to the events, never read by the engine,
 * the insights, the agents or the chat. Coordinates are the events' (home attacks x = 105 in
 * both halves); the second half is turned on screen like everything else (see inHalf in play.ts).
 */

export interface PositionsFile {
  match_id: string;
  illustrative: true;
  /** Frames per match second. */
  hz: number;
  teams: Record<'home' | 'away', { name: string; players: { slot: number; player: string; number: number; position: string }[] }>;
  lineup_changes: { t_s: number; team: 'home' | 'away'; slot: number; player_out: string; player_in: string; number: number; position: string }[];
  set_pieces: { t_s: number; kind: string; team: 'home' | 'away'; taker: string; spot: PitchPoint; ball_out_from_t_s: number }[];
  frames: { t: number; b: PitchPoint; h: PitchPoint[]; a: PitchPoint[] }[];
}

export interface PitchFrame {
  ball: PitchPoint;
  home: PitchPoint[];
  away: PitchPoint[];
}

const lerp = (a: PitchPoint, b: PitchPoint, f: number): PitchPoint => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];

/** Where everyone is at match second t, between the two frames around it. */
export function frameAt(file: PositionsFile, t: number): PitchFrame | null {
  const frames = file.frames;
  if (!frames.length) return null;
  const step = 1 / file.hz;
  const i = Math.max(0, Math.min(frames.length - 1, Math.floor((t - frames[0].t) / step)));
  const a = frames[i];
  const b = frames[Math.min(frames.length - 1, i + 1)];
  const f = b.t > a.t ? Math.max(0, Math.min(1, (t - a.t) / (b.t - a.t))) : 0;
  return {
    ball: lerp(a.b, b.b, f),
    home: a.h.map((p, k) => lerp(p, b.h[k], f)),
    away: a.a.map((p, k) => lerp(p, b.a[k], f)),
  };
}

export interface OnPitch {
  player: string;
  number: number;
  position: string;
}

/** Who stands in each slot at second t, after the substitutions made by then. */
export function lineupAt(file: PositionsFile, t: number): Record<'home' | 'away', OnPitch[]> {
  const out = {
    home: file.teams.home.players.map(({ player, number, position }) => ({ player, number, position })),
    away: file.teams.away.players.map(({ player, number, position }) => ({ player, number, position })),
  };
  for (const c of file.lineup_changes) {
    if (c.t_s <= t) out[c.team][c.slot] = { player: c.player_in, number: c.number, position: c.position };
  }
  return out;
}
