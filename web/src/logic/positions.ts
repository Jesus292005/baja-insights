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

/** Furthest a curved path may stray from the straight one between two frames, in metres. */
const MAX_BEND = 0.4;

/**
 * A player's point between frames p1 and p2 on a Catmull-Rom curve through p0..p3. Straight lines
 * between 2 Hz frames change speed every half second (a visible jerk); the curve keeps the speed
 * continuous and still passes through every frame, so each event's player stays on its point. Its
 * bend is capped and it stays on the pitch, so a sharp turn never swings wide.
 */
function curve(p0: PitchPoint, p1: PitchPoint, p2: PitchPoint, p3: PitchPoint, f: number): PitchPoint {
  const f2 = f * f;
  const f3 = f2 * f;
  const at = (k: 0 | 1) =>
    0.5 * (2 * p1[k] + (p2[k] - p0[k]) * f + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * f2 + (3 * p1[k] - p0[k] - 3 * p2[k] + p3[k]) * f3);
  const line = lerp(p1, p2, f);
  let x = at(0);
  let y = at(1);
  const bend = Math.hypot(x - line[0], y - line[1]);
  if (bend > MAX_BEND) {
    x = line[0] + ((x - line[0]) * MAX_BEND) / bend;
    y = line[1] + ((y - line[1]) * MAX_BEND) / bend;
  }
  return [Math.max(0, Math.min(105, x)), Math.max(0, Math.min(68, y))];
}

/**
 * Where everyone is at match second t. Players follow a curve through the frames around t; the
 * ball goes straight, since passes and shots are straight lines.
 */
export function frameAt(file: PositionsFile, t: number): PitchFrame | null {
  const frames = file.frames;
  if (!frames.length) return null;
  const last = frames.length - 1;
  const step = 1 / file.hz;
  const i = Math.max(0, Math.min(last, Math.floor((t - frames[0].t) / step)));
  const [f0, a, b, f3] = [frames[Math.max(0, i - 1)], frames[i], frames[Math.min(last, i + 1)], frames[Math.min(last, i + 2)]];
  const f = b.t > a.t ? Math.max(0, Math.min(1, (t - a.t) / (b.t - a.t))) : 0;
  const players = (side: 'h' | 'a') => a[side].map((p, k) => curve(f0[side][k], p, b[side][k], f3[side][k], f));
  return { ball: lerp(a.b, b.b, f), home: players('h'), away: players('a') };
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
