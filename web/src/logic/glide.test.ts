import { describe, expect, it } from 'vitest';
import { GlideClock } from './glide';

/** Ticks of a clock at `speed`, every ~100 ms with some jitter, drawn every 16 ms. */
function run(speed: number, jitter: number) {
  const clock = new GlideClock();
  let t = 1000;
  let now = 0;
  let nextTick = 0;
  const drawn: number[] = [];
  const truth: number[] = [];
  for (let frame = 0; frame < 300; frame++) {
    now = frame * 16;
    if (now >= nextTick) {
      t = 1000 + (now / 1000) * speed;
      clock.update(t, now);
      nextTick = now + 100 + (frame % 3 === 0 ? jitter : -jitter);
    }
    drawn.push(clock.value(now));
    truth.push(1000 + (now / 1000) * speed);
  }
  return { drawn, truth };
}

describe('GlideClock', () => {
  it('never goes backwards, even with uneven ticks', () => {
    for (const speed of [1, 2, 60]) {
      const { drawn } = run(speed, 30);
      for (let i = 1; i < drawn.length; i++) expect(drawn[i]).toBeGreaterThanOrEqual(drawn[i - 1]);
    }
  });

  it('stays close to the match clock', () => {
    for (const speed of [1, 60]) {
      const { drawn, truth } = run(speed, 20);
      const worst = Math.max(...drawn.slice(30).map((d, i) => Math.abs(d - truth[i + 30])));
      // Within a quarter of a tick of match time.
      expect(worst).toBeLessThan(speed * 0.25);
    }
  });

  it('jumps on a seek and holds when paused', () => {
    const clock = new GlideClock();
    clock.update(100, 0);
    clock.update(100.1, 100);
    clock.update(3000, 200);
    expect(clock.value(200)).toBe(3000);
    clock.update(3000, 300, true);
    expect(clock.value(900)).toBe(3000);
  });
});
