import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { frameAt, lineupAt, type PositionsFile } from './positions';

const sample = JSON.parse(readFileSync(resolve(__dirname, '../../../mocks/positions_sample.json'), 'utf8')) as PositionsFile;

describe('frameAt', () => {
  it('returns a frame exactly on its second', () => {
    const f = sample.frames[10];
    expect(frameAt(sample, f.t)).toEqual({ ball: f.b, home: f.h, away: f.a });
  });

  it('places the ball halfway between two frames, and the players near halfway', () => {
    const [a, b] = [sample.frames[20], sample.frames[21]];
    const mid = frameAt(sample, (a.t + b.t) / 2)!;
    expect(mid.ball[0]).toBeCloseTo((a.b[0] + b.b[0]) / 2);
    expect(Math.abs(mid.home[3][1] - (a.h[3][1] + b.h[3][1]) / 2)).toBeLessThanOrEqual(0.4);
  });

  it('holds the first and last frames outside the file', () => {
    expect(frameAt(sample, 0)!.ball).toEqual(sample.frames[0].b);
    expect(frameAt(sample, 99999)!.ball).toEqual(sample.frames.at(-1)!.b);
  });
});

describe('lineupAt', () => {
  it('swaps a substitute into the slot from the minute of the change', () => {
    const file = {
      ...sample,
      lineup_changes: [{ t_s: 4200, team: 'away', slot: 8, player_out: 'X', player_in: 'R. Amador', number: 17, position: 'ED' }],
    } as PositionsFile;
    expect(lineupAt(file, 4199).away[8].player).toBe(sample.teams.away.players[8].player);
    expect(lineupAt(file, 4200).away[8]).toEqual({ player: 'R. Amador', number: 17, position: 'ED' });
  });
});

describe('frameAt, smooth paths', () => {
  const speedJump = (at: (t: number) => [number, number], t: number) => {
    const e = 0.01;
    const vIn = [(at(t)[0] - at(t - e)[0]) / e, (at(t)[1] - at(t - e)[1]) / e];
    const vOut = [(at(t + e)[0] - at(t)[0]) / e, (at(t + e)[1] - at(t)[1]) / e];
    return Math.hypot(vOut[0] - vIn[0], vOut[1] - vIn[1]);
  };

  it('keeps the speed of each player continuous through a frame', () => {
    const mid = sample.frames[30].t;
    for (let k = 0; k < 11; k++) {
      const at = (t: number) => frameAt(sample, t)!.home[k] as [number, number];
      expect(speedJump(at, mid)).toBeLessThan(0.5);
    }
  });

  it('never strays far from the straight path, nor off the pitch', () => {
    for (let i = 1; i < sample.frames.length - 2; i++) {
      const [a, b] = [sample.frames[i], sample.frames[i + 1]];
      for (const f of [0.25, 0.5, 0.75]) {
        const p = frameAt(sample, a.t + (b.t - a.t) * f)!;
        p.home.concat(p.away).forEach(([x, y], k) => {
          const side = k < 11 ? 'h' : 'a';
          const [p1, p2] = [a[side][k % 11], b[side][k % 11]];
          const lx = p1[0] + (p2[0] - p1[0]) * f;
          const ly = p1[1] + (p2[1] - p1[1]) * f;
          expect(Math.hypot(x - lx, y - ly)).toBeLessThanOrEqual(0.4001);
          expect(x >= 0 && x <= 105 && y >= 0 && y <= 68).toBe(true);
        });
      }
    }
  });
});
