import { describe, expect, it } from 'vitest';
import { demoMatch, roster } from '../data/match';
import { forViewer } from './derive';
import { placeCards, playPoints, svgToCanvas } from './dodge';
import { playAt } from './play';

const inside = (b: { x: number; y: number; w: number; h: number }, [x, y]: [number, number]) =>
  x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h;

describe('placeCards', () => {
  const card = { key: 'top_right', home: { x: 1344, y: 54, w: 480, h: 300 } };

  it('keeps a card in its slot when the play is elsewhere', () => {
    const play: [number, number][] = [[300, 700], [400, 750]];
    expect(placeCards([card], play, [])).toEqual(new Map([['top_right', card.home]]));
  });

  it('moves a card off the play, and never onto the score bug', () => {
    const play: [number, number][] = Array.from({ length: 20 }, (_, i) => [1400 + i * 20, 100 + i * 10]);
    const bug = { x: 96, y: 54, w: 520, h: 100 };
    const box = placeCards([card], play, [bug]).get('top_right')!;
    expect(play.filter((p) => inside(box, p))).toEqual([]);
    expect(box.x < bug.x + bug.w && bug.x < box.x + box.w && box.y < bug.y + bug.h && bug.y < box.y + box.h).toBe(false);
  });
});

describe('playPoints', () => {
  it('maps the pitch centre to the middle of the canvas', () => {
    const [x, y] = svgToCanvas([525, 340]);
    expect(Math.round(x)).toBe(960);
    expect(Math.round(y)).toBe(540);
  });

  it('gives points for the lines and names of a real play', () => {
    const fan = forViewer(demoMatch.overlays, 'fan', 'en');
    const goal = fan.find((o) => o.type === 'goal_analysis')!;
    const pts = playPoints(playAt(fan, goal.show_at_s, demoMatch.playEvents, roster)!);
    expect(pts.length).toBeGreaterThan(20);
    for (const [x, y] of pts) {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(1920);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(1080);
    }
  });
});
