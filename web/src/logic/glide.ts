/**
 * A display clock for the players: the match clock arrives in steps (every 100 ms, 6 match seconds
 * at 60×), and drawing those steps as they come makes the players stutter. This clock moves on
 * every frame, never goes backwards and never jumps on a step: at each new value it sets its pace
 * to land where the match will be when the next value is due.
 */
export class GlideClock {
  private base = 0;
  private at = 0;
  private pace = 0;
  /** Match speed, averaged over the last steps: each value is seen up to a frame late, so one step alone is noisy. */
  private speed = 0;
  private last: { t: number; at: number } | null = null;

  /**
   * @param stepS Seconds between clock values (the replay ticks every 100 ms).
   * @param seekS A bigger change (match seconds) is a seek: jump there instead of gliding.
   * @param catchUp Steps over which a gap to the match clock is closed: more is smoother, less is tighter.
   */
  constructor(private readonly stepS = 0.1, private readonly seekS = 20, private readonly catchUp = 3) {}

  /** Match second to draw at `now` (ms, performance.now()). Stops a little after the last value if no new one comes. */
  value(now: number): number {
    return this.base + this.pace * Math.min(Math.max(0, (now - this.at) / 1000), this.stepS * this.catchUp);
  }

  /** A new match clock value. `hold` (paused, or a frozen moment) shows it as it is. */
  update(t: number, now: number, hold = false): void {
    const prev = this.last;
    this.last = { t, at: now };
    const shown = prev ? this.value(now) : t;
    if (hold || !prev || t < prev.t || Math.abs(t - shown) > this.seekS) {
      this.base = t;
      this.at = now;
      this.pace = 0;
      this.speed = 0;
      return;
    }
    const dt = (now - prev.at) / 1000;
    const step = dt > 0 ? (t - prev.t) / dt : 0;
    // A change of pace (60× between moments, 1× during one) is taken at once; small noise is averaged.
    this.speed = this.speed === 0 || Math.abs(step - this.speed) > this.speed * 0.5 ? step : this.speed * 0.7 + step * 0.3;
    // Glide from where we are towards where the match will be, closing the gap over a few steps.
    const span = this.stepS * this.catchUp;
    const goal = t + this.speed * span;
    this.base = shown;
    this.at = now;
    this.pace = Math.max(0, (goal - shown) / span);
  }
}
