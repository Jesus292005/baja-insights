import type { ChainLink, Language, OverlayCard } from '../contracts/overlay';

/**
 * Labels the engine sends as data (contract v1.1), written in each language.
 * Spanish uses the engine's own text when it comes (`action`, `reason`); the other languages are
 * built from `type` and `reason_code`, with the Spanish text as the last fallback.
 * Rules: docs/cambios-motor-realismo.md, section 5, and contracts/README.md.
 */

const EN_CARDINAL = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const EN_ORDINAL = ['', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth'];
const ES_CARDINAL = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez'];
const ES_ORDINAL_F = ['', 'primera', 'segunda', 'tercera', 'cuarta', 'quinta', 'sexta', 'séptima', 'octava', 'novena', 'décima'];

/** Small counts in words, so a fan text keeps a single figure (the engine does the same). */
const word = (n: number, table: string[]) => (Number.isInteger(n) && n >= 0 && n < table.length && table[n] ? table[n] : String(n));

/* ---------- Goal chain ---------- */

const LINK_EN: Partial<Record<NonNullable<ChainLink['type']>, string>> = {
  recovery: 'recovery',
  tackle: 'tackle won',
  shot: 'shot',
  off_ball_run: 'off-ball run that dragged a marker',
  duel: 'duel won',
  pressure: 'pressure',
  foul: 'foul won',
};

const LINK_ES: Partial<Record<NonNullable<ChainLink['type']>, string>> = {
  recovery: 'recuperación',
  tackle: 'entrada ganada',
  shot: 'remate',
  off_ball_run: 'desmarque y arrastre de marca',
};

function passLabel(lines: number, cross: boolean, lang: Language): string {
  if (cross) return lang === 'es' ? 'centro' : 'cross';
  if (lines >= 1) {
    if (lang === 'es') return `pase que rompió ${lines} ${lines === 1 ? 'línea' : 'líneas'}`;
    return `pass that broke ${lines} ${lines === 1 ? 'line' : 'lines'}`;
  }
  return lang === 'es' ? 'pase' : 'pass';
}

/** What a link of the goal chain did, in the viewer's language. */
export function chainActionLabel(link: ChainLink, lang: Language): string {
  if (lang === 'es' && link.action) return link.action;
  if (!link.type) return link.action;
  if (link.type === 'pass') return passLabel(link.lines_broken ?? 0, link.cross === true, lang);
  const table = lang === 'es' ? LINK_ES : LINK_EN;
  return table[link.type] ?? link.action;
}

/* ---------- Card reason ---------- */

type Params = NonNullable<OverlayCard['reason_params']>;
const num = (p: Params, k: string) => (typeof p[k] === 'number' ? (p[k] as number) : null);
const str = (p: Params, k: string) => (typeof p[k] === 'string' ? (p[k] as string) : null);

/** English text by reason code. Returns null when a needed parameter is missing. */
function reasonEn(code: NonNullable<OverlayCard['reason_code']>, p: Params): string | null {
  switch (code) {
    case 'line_breaking_pass': {
      const lines = num(p, 'lines');
      if (lines === null) return null;
      return `pass that broke ${lines} ${lines === 1 ? 'line' : 'lines'}${p.under_pressure === true ? ' under pressure' : ''}`;
    }
    case 'opp_half_recoveries': {
      const count = num(p, 'count');
      const win = num(p, 'window_min');
      if (count === null || win === null) return null;
      return `${word(count, EN_ORDINAL)} recovery in the opposition half in under ${win} minutes`;
    }
    case 'shot_speed': {
      const v = num(p, 'speed_kmh');
      return v === null ? null : `shot at ${v} km/h`;
    }
    case 'duel_streak': {
      const count = num(p, 'count');
      return count === null ? null : `${count} duels won in a row`;
    }
    case 'run_speed': {
      const v = num(p, 'speed_kmh');
      return v === null ? null : `run at ${v} km/h`;
    }
    case 'dribbles': {
      const count = num(p, 'count');
      const win = num(p, 'window_min');
      if (count === null || win === null) return null;
      return `${word(count, EN_CARDINAL)} dribbles won in under ${win} minutes`;
    }
    case 'run_ended_in_shot': {
      const who = str(p, 'dragged_defender');
      return who === null ? null : `dragged ${who} and the move ended in a shot`;
    }
    case 'run_opened_goal': {
      const who = str(p, 'dragged_position') === 'DFC' ? 'the centre back' : str(p, 'dragged_defender');
      return who === null ? null : `dragged ${who} and opened the space for the goal`;
    }
    case 'standout_defensive':
      return 'defensive game above what the role expects';
    case 'standout_creative':
      return 'creative game above what the role expects';
    case 'pass_streak': {
      const count = num(p, 'count');
      return count === null ? null : `${count} passes completed in a row`;
    }
    case 'recovery_to_shot': {
      const secs = num(p, 'seconds');
      return secs === null ? null : `won the ball in his own half and the team shot ${secs} seconds later`;
    }
    case 'big_save': {
      const xg = num(p, 'xg');
      if (xg === null) return null;
      const who = str(p, 'shooter');
      return who ? `save from ${who}'s shot of xG ${xg.toFixed(2)}` : `save from a shot of xG ${xg.toFixed(2)}`;
    }
  }
}

/** Spanish text by reason code, the same wording the engine uses. Only used when `reason` is missing. */
function reasonEs(code: NonNullable<OverlayCard['reason_code']>, p: Params): string | null {
  switch (code) {
    case 'line_breaking_pass': {
      const lines = num(p, 'lines');
      if (lines === null) return null;
      return `pase que rompió ${lines} ${lines === 1 ? 'línea' : 'líneas'}${p.under_pressure === true ? ' bajo presión' : ''}`;
    }
    case 'opp_half_recoveries': {
      const count = num(p, 'count');
      const win = num(p, 'window_min');
      if (count === null || win === null) return null;
      return `${word(count, ES_ORDINAL_F)} recuperación en campo rival en menos de ${win} minutos`;
    }
    case 'shot_speed': {
      const v = num(p, 'speed_kmh');
      return v === null ? null : `remate a ${v} km/h`;
    }
    case 'duel_streak': {
      const count = num(p, 'count');
      return count === null ? null : `${count} duelos ganados seguidos`;
    }
    case 'run_speed': {
      const v = num(p, 'speed_kmh');
      return v === null ? null : `desmarque a ${v} km/h`;
    }
    case 'dribbles': {
      const count = num(p, 'count');
      const win = num(p, 'window_min');
      if (count === null || win === null) return null;
      return `${word(count, ES_CARDINAL)} regates ganados en menos de ${win} minutos`;
    }
    case 'run_ended_in_shot': {
      const who = str(p, 'dragged_defender');
      return who === null ? null : `arrastró a ${who} y la jugada terminó en remate`;
    }
    case 'run_opened_goal': {
      const who = str(p, 'dragged_position') === 'DFC' ? 'al central' : str(p, 'dragged_defender') && `a ${str(p, 'dragged_defender')}`;
      return who ? `arrastró ${who} y abrió el espacio del gol` : null;
    }
    case 'standout_defensive':
      return 'partido defensivo por encima de lo esperado para su rol';
    case 'standout_creative':
      return 'partido creativo por encima de lo esperado para su rol';
    case 'pass_streak': {
      const count = num(p, 'count');
      return count === null ? null : `${count} pases completados seguidos`;
    }
    case 'recovery_to_shot': {
      const secs = num(p, 'seconds');
      return secs === null ? null : `recuperación en campo propio que terminó en remate en ${secs} segundos`;
    }
    case 'big_save': {
      const xg = num(p, 'xg');
      return xg === null ? null : `atajada a un remate de xG ${xg.toFixed(2)}`;
    }
  }
}

/** Why a card attribute went up, in the viewer's language. null when the order carries no reason at all. */
export function cardReasonLabel(card: Pick<OverlayCard, 'reason' | 'reason_code' | 'reason_params'>, lang: Language): string | null {
  const params = card.reason_params ?? {};
  if (lang === 'es') {
    if (card.reason) return card.reason;
    return card.reason_code ? reasonEs(card.reason_code, params) : null;
  }
  const en = card.reason_code ? reasonEn(card.reason_code, params) : null;
  return en ?? card.reason ?? null;
}
