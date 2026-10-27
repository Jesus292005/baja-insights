import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { frameAt, lineupAt, type PositionsFile } from './positions';

/** The real match: each event's player must stand on the event's point in our frames and lineup. */
const dir = resolve(__dirname, '../../../data/m001');
const file = JSON.parse(readFileSync(resolve(dir, 'positions.json'), 'utf8')) as PositionsFile;
const events = readFileSync(resolve(dir, 'events.jsonl'), 'utf8')
  .split(/\r?\n/)
  .filter(Boolean)
  .map((l) => JSON.parse(l) as { t_s: number; team: string | null; player: string | null; start: [number, number] | null });

describe('positions of m001', () => {
  it('put the player of each event on its point', () => {
    const home = file.teams.home.name;
    const misses: string[] = [];
    let checked = 0;
    for (const e of events) {
      if (!e.player || !e.team || !Array.isArray(e.start)) continue;
      const side = e.team === home ? 'home' : 'away';
      const slot = lineupAt(file, e.t_s)[side].findIndex((p) => p.player === e.player);
      if (slot < 0) {
        misses.push(`${e.t_s} ${e.player} not on the pitch`);
        continue;
      }
      const [x, y] = frameAt(file, e.t_s)![side][slot];
      checked++;
      if (Math.hypot(x - e.start[0], y - e.start[1]) > 4) misses.push(`${e.t_s} ${e.player}`);
    }
    expect(checked).toBeGreaterThan(1000);
    // The model places a couple of events up to 4 m off (aviso-22-jugadores.md); allow a handful.
    expect(misses.length).toBeLessThan(10);
  });
});
