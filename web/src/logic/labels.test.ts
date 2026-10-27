import { describe, expect, it } from 'vitest';
import type { ChainLink } from '../contracts/overlay';
import { placeLabels, textBox } from './labels';
import { buildPlay, PITCH_H, PITCH_W } from './play';

const link = (player: string, t_s: number, type: string, start: [number, number], end?: [number, number]) =>
  ({ event_id: `e${t_s}`, player, action: '', credit: 0, t_s, type, start, end }) as unknown as ChainLink;

const boxes = (links: ChainLink[], names: string[]) => {
  const drawn = buildPlay(links, true);
  const spots = placeLabels(drawn, names, null);
  return drawn.labels.map((l, i) => textBox(names[i], 'player', spots.players.get(l.link)!));
};

const overlap = (a: { x: number; y: number; w: number; h: number }, b: typeof a) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

describe('placeLabels', () => {
  it('keeps the names of players close together apart', () => {
    const links = [
      link('A. Olvera', 1, 'pass', [50, 30], [52, 31]),
      link('B. Félix', 2, 'pass', [52, 31], [54, 30]),
      link('C. Haro', 3, 'pass', [54, 30], [53, 32]),
    ];
    const [a, b, c] = boxes(links, ['Olvera', 'Félix', 'Haro']);
    expect(overlap(a, b)).toBe(false);
    expect(overlap(a, c)).toBe(false);
    expect(overlap(b, c)).toBe(false);
  });

  it('keeps names inside the drawing near the corners', () => {
    const links = [link('D. Ramírez', 1, 'shot', [104, 67], [105, 34]), link('E. Cota', 2, 'recovery', [1, 1])];
    for (const b of boxes(links, ['Ramírez', 'Cota'])) {
      expect(b.x).toBeGreaterThanOrEqual(-24);
      expect(b.y).toBeGreaterThanOrEqual(-24);
      expect(b.x + b.w).toBeLessThanOrEqual(PITCH_W + 24);
      expect(b.y + b.h).toBeLessThanOrEqual(PITCH_H + 24);
    }
  });
});
