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

  it('places everyone halfway between two frames', () => {
    const [a, b] = [sample.frames[20], sample.frames[21]];
    const mid = frameAt(sample, (a.t + b.t) / 2)!;
    expect(mid.ball[0]).toBeCloseTo((a.b[0] + b.b[0]) / 2);
    expect(mid.home[3][1]).toBeCloseTo((a.h[3][1] + b.h[3][1]) / 2);
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
