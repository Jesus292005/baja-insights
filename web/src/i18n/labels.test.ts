import { describe, expect, it } from 'vitest';
import type { ChainLink, OverlayOrder, ReasonCode } from '../contracts/overlay';
import { demoMatch } from '../data/match';
import { cardReasonLabel, chainActionLabel } from './labels';

const link = (extra: Partial<ChainLink>): ChainLink => ({ event_id: 1, player: 'X', action: 'acción', credit: 0.25, t_s: 10, ...extra });

describe('chainActionLabel', () => {
  it('keeps the engine Spanish text', () => {
    expect(chainActionLabel(link({ type: 'pass', lines_broken: 2, action: 'pase que rompió 2 líneas' }), 'es')).toBe('pase que rompió 2 líneas');
  });

  it('builds English from type, lines and cross', () => {
    expect(chainActionLabel(link({ type: 'pass', lines_broken: 2 }), 'en')).toBe('pass that broke 2 lines');
    expect(chainActionLabel(link({ type: 'pass', lines_broken: 1 }), 'en')).toBe('pass that broke 1 line');
    expect(chainActionLabel(link({ type: 'pass', lines_broken: 1, cross: true }), 'en')).toBe('cross');
    expect(chainActionLabel(link({ type: 'pass', lines_broken: 0 }), 'en')).toBe('pass');
    expect(chainActionLabel(link({ type: 'recovery' }), 'en')).toBe('recovery');
    expect(chainActionLabel(link({ type: 'tackle' }), 'en')).toBe('tackle won');
    expect(chainActionLabel(link({ type: 'off_ball_run' }), 'en')).toBe('off-ball run that dragged a marker');
  });

  it('falls back to the engine text when type is missing (v1 orders)', () => {
    expect(chainActionLabel(link({ action: 'remate' }), 'en')).toBe('remate');
  });

  it('has an English label for every link of the demo match', () => {
    const links = demoMatch.overlays.flatMap((o) => (o.type === 'goal_analysis' ? o.data.chain_detail ?? [] : []));
    expect(links.length).toBeGreaterThan(0);
    for (const l of links) expect(chainActionLabel(l, 'en')).not.toBe(l.action);
  });
});

describe('cardReasonLabel', () => {
  it('uses the engine reason in Spanish', () => {
    expect(cardReasonLabel({ reason: 'remate a 112 km/h', reason_code: 'shot_speed', reason_params: { speed_kmh: 112 } }, 'es')).toBe('remate a 112 km/h');
  });

  it('writes English from the code, with counts in words where the engine uses words', () => {
    const en = (reason_code: ReasonCode, reason_params: Record<string, number | string | boolean>) => cardReasonLabel({ reason_code, reason_params }, 'en');
    expect(en('line_breaking_pass', { lines: 2, under_pressure: true })).toBe('pass that broke 2 lines under pressure');
    expect(en('opp_half_recoveries', { count: 3, window_min: 10 })).toBe('third recovery in the opposition half in under 10 minutes');
    expect(en('dribbles', { count: 2, window_min: 10 })).toBe('two dribbles won in under 10 minutes');
    expect(en('duel_streak', { count: 4 })).toBe('4 duels won in a row');
    expect(en('run_opened_goal', { dragged_defender: 'G. Cárdenas', dragged_position: 'DFC' })).toBe('dragged the centre back and opened the space for the goal');
    expect(en('run_ended_in_shot', { dragged_defender: 'T. Esquer' })).toBe('dragged T. Esquer and the move ended in a shot');
    expect(en('standout_creative', {})).toBe('creative game above what the role expects');
  });

  it('builds Spanish from the code only when reason is missing, matching the engine wording', () => {
    const cards = demoMatch.overlays.flatMap((o: OverlayOrder) => (o.card?.reason && o.card.reason_code ? [o.card] : []));
    expect(cards.length).toBeGreaterThan(0);
    for (const c of cards) expect(cardReasonLabel({ reason_code: c.reason_code, reason_params: c.reason_params }, 'es')).toBe(c.reason);
  });

  it('falls back to the Spanish reason when the code or a parameter is missing, and to null with nothing', () => {
    expect(cardReasonLabel({ reason: 'texto del motor' }, 'en')).toBe('texto del motor');
    expect(cardReasonLabel({ reason: 'texto', reason_code: 'shot_speed', reason_params: {} }, 'en')).toBe('texto');
    expect(cardReasonLabel({}, 'en')).toBeNull();
  });

  it('has an English text for every card of the demo match', () => {
    const cards = demoMatch.overlays.flatMap((o) => (o.card?.reason_code ? [o.card] : []));
    for (const c of cards) expect(cardReasonLabel(c, 'en')).not.toBe(c.reason);
  });
});
