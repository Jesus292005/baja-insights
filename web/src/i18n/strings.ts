/**
 * Microcopy de la interfaz en español e inglés.
 * Solo textos de la UI. Los títulos y textos de cada gráfico vienen escritos por los agentes
 * en la orden (`title`, `text`) y la interfaz no los traduce ni los modifica.
 *
 * Variables entre llaves: {clock}, {player}, {from}, {to}, {ids}, {tools}, {query}, {seconds}.
 */
import type { CardAttribute, Language, Position } from '../contracts/overlay';

const es = {
  app: {
    name: 'Baja-Insights',
    tagline: 'El marcador no cuenta toda la historia.',
    fiction: 'Equipos, jugadores y datos ficticios.',
    skipToMatch: 'Saltar al partido',
  },
  mode: {
    label: 'Modo',
    fan: 'Aficionado',
    analyst: 'Analista',
    fanHint: 'La historia del partido, sin tecnicismos.',
    analystHint: 'Todas las cifras, con su evidencia.',
  },
  language: { label: 'Idioma', es: 'Español', en: 'English' },
  status: {
    connecting: 'Conectando con el partido…',
    live: 'En vivo',
    reconnecting: 'Reconectando. Mostramos los datos hasta el {clock}.',
    reconnectingIn: 'Nuevo intento en {seconds} s',
    offline: 'Se perdió la conexión con el partido.',
    offlineBody: 'Lo que ves es el último dato confirmado, del {clock}.',
    retry: 'Reintentar',
    replay: 'Repetición',
    preMatch: 'El partido aún no empieza.',
    halfTime: 'Medio tiempo',
    fullTime: 'Final',
    asOf: 'Dato del {clock}',
    updated: 'Actualizado',
  },
  mvp: {
    title: 'Carrera por el MVP',
    score: 'Puntaje MVP',
    leader: 'Líder',
    rankUp: 'Sube del {from} al {to}',
    newEntry: 'Entra al {to}',
    empty: 'Aún no hay movimientos. La carrera aparece cuando alguien sube de puesto.',
    partial: 'Solo vemos el último movimiento. El ranking completo llega con la próxima actualización.',
  },
  duel: {
    title: 'Duelo de banda',
    even: 'Parejo',
    ahead: 'Ventaja {player}',
    vsRole: 'vs. su rol',
    legend: 'La barra compara a cada jugador con lo que se espera de su posición.',
    empty: 'Todavía no hay duelos directos. La barra se mueve con el primero.',
  },
  milestone: {
    label: 'Hito',
    expected: 'Esperado para su rol',
    aboveRole: 'sobre su rol',
    belowRole: 'bajo su rol',
  },
  card: {
    levelUp: 'Sube de nivel',
    overall: 'Media',
    base: 'Carta inicial',
    noChanges: 'Sin cambios todavía.',
    overallPending: 'Media sin dato',
    tier: { arena: 'Arena', coral: 'Coral', perla: 'Perla', ballena: 'Ballena' },
  },
  goal: {
    title: 'Cadena del gol',
    credit: 'Crédito',
    invisible: 'Asistencia invisible',
    invisibleHint: 'Influyó en el gol sin tocar el balón.',
    empty: 'Todavía no hay goles.',
  },
  phase: { control: 'Control', pressure_shift: 'Cambio de presión', defHeight: 'Altura de acciones defensivas' },
  keys: {
    title: 'Claves del partido',
    noPrediction: 'No hacemos predicciones. Mostramos qué necesita cada equipo.',
    xg: 'xG',
    possession: 'Posesión',
  },
  top3: {
    title: '¿Quién ganó realmente?',
    pending: 'El top 3 se publica al final del partido.',
  },
  chat: {
    title: 'Pregúntale al partido',
    intro: 'Responde solo con los datos de este partido. Si algo no se mide, te lo dice.',
    placeholder: 'Pregunta por un jugador, un duelo o un gol',
    send: 'Preguntar',
    sending: 'Consultando los datos del partido…',
    answeredWith: 'Respondido con: {tools}',
    notTracked: 'Ese dato no se mide en este partido.',
    notFound: 'No encontramos «{query}» en este partido. Revisa el nombre.',
    noPrediction: 'Sin predicciones: solo lo que ya pasó.',
    error: 'No pudimos consultar el partido. Tu pregunta sigue aquí, inténtalo de nuevo.',
    offline: 'El chat vuelve cuando se recupere la conexión.',
    suggestions: ['¿Cómo va el partido?', '¿Quién gana el duelo de banda?', '¿Quién hizo la asistencia invisible?'],
    suggestionLeader: '¿Por qué {player} va primero?',
  },
  evidence: {
    label: 'Evidencia',
    events: 'Jugadas {ids}',
    engine: 'Dato del motor',
    engineHint: 'Calculado con reglas fijas a partir de los eventos. La IA no cambia esta cifra.',
  },
  timeline: {
    title: 'Momentos',
    empty: 'Los momentos clave aparecen aquí conforme pasan.',
    replay: 'Ver otra vez',
  },
  noData: { short: '—', a11y: 'Sin dato' },
  units: { minute: 'min', second: 's', meters: 'm', pct: '%' },
} as const;

type Shape<T> = { [K in keyof T]: T[K] extends string ? string : T[K] extends readonly string[] ? readonly string[] : Shape<T[K]> };

const en: Shape<typeof es> = {
  app: {
    name: 'Baja-Insights',
    tagline: "The scoreline doesn't tell the whole story.",
    fiction: 'Fictional teams, players and data.',
    skipToMatch: 'Skip to the match',
  },
  mode: {
    label: 'Mode',
    fan: 'Fan',
    analyst: 'Analyst',
    fanHint: 'The story of the match, no jargon.',
    analystHint: 'Every number, with its evidence.',
  },
  language: { label: 'Language', es: 'Español', en: 'English' },
  status: {
    connecting: 'Connecting to the match…',
    live: 'Live',
    reconnecting: 'Reconnecting. Showing data up to {clock}.',
    reconnectingIn: 'Next try in {seconds} s',
    offline: 'Lost the connection to the match.',
    offlineBody: "What you see is the last confirmed data, from {clock}.",
    retry: 'Try again',
    replay: 'Replay',
    preMatch: "The match hasn't started yet.",
    halfTime: 'Half-time',
    fullTime: 'Full-time',
    asOf: 'As of {clock}',
    updated: 'Updated',
  },
  mvp: {
    title: 'MVP race',
    score: 'MVP score',
    leader: 'Leader',
    rankUp: 'Up from {from} to {to}',
    newEntry: 'In at {to}',
    empty: 'No moves yet. The race shows up when someone climbs.',
    partial: 'Showing the latest move only. The full ranking arrives with the next update.',
  },
  duel: {
    title: 'Flank duel',
    even: 'Even',
    ahead: '{player} ahead',
    vsRole: 'vs. role',
    legend: "The bar compares each player with what's expected for their position.",
    empty: 'No head-to-head duels yet. The bar moves after the first one.',
  },
  milestone: {
    label: 'Milestone',
    expected: 'Expected for the role',
    aboveRole: 'above role',
    belowRole: 'below role',
  },
  card: {
    levelUp: 'Level up',
    overall: 'Overall',
    base: 'Starting card',
    noChanges: 'No changes yet.',
    overallPending: 'Overall not available',
    tier: { arena: 'Sand', coral: 'Coral', perla: 'Pearl', ballena: 'Whale' },
  },
  goal: {
    title: 'Goal chain',
    credit: 'Credit',
    invisible: 'Invisible assist',
    invisibleHint: 'Shaped the goal without touching the ball.',
    empty: 'No goals yet.',
  },
  phase: { control: 'Control', pressure_shift: 'Pressure shift', defHeight: 'Defensive action height' },
  keys: {
    title: 'Match keys',
    noPrediction: "We don't make predictions. We show what each team needs.",
    xg: 'xG',
    possession: 'Possession',
  },
  top3: {
    title: 'Who really won?',
    pending: 'The top 3 is published at full-time.',
  },
  chat: {
    title: 'Ask the match',
    intro: "Answers only from this match's data. If something isn't tracked, it says so.",
    placeholder: 'Ask about a player, a duel or a goal',
    send: 'Ask',
    sending: 'Checking the match data…',
    answeredWith: 'Answered with: {tools}',
    notTracked: "That isn't tracked in this match.",
    notFound: "We couldn't find “{query}” in this match. Check the name.",
    noPrediction: 'No predictions, only what has happened.',
    error: "We couldn't reach the match data. Your question is still here, try again.",
    offline: 'Chat comes back when the connection does.',
    suggestions: ["How's the match going?", "Who's winning the flank duel?", 'Who made the invisible assist?'],
    suggestionLeader: 'Why is {player} first?',
  },
  evidence: {
    label: 'Evidence',
    events: 'Plays {ids}',
    engine: 'Engine data',
    engineHint: 'Calculated with fixed rules from the events. The AI never changes this number.',
  },
  timeline: {
    title: 'Moments',
    empty: 'Key moments show up here as they happen.',
    replay: 'Show again',
  },
  noData: { short: '—', a11y: 'No data' },
  units: { minute: 'min', second: 's', meters: 'm', pct: '%' },
};

export const strings = { es, en } as const;
export type Strings = Shape<typeof es>;

export const attributeLabel: Record<Language, Record<CardAttribute, string>> = {
  es: { ritmo: 'Ritmo', disparo: 'Disparo', vision: 'Visión', regate: 'Regate', defensa: 'Defensa', fisico: 'Físico', sin_balon: 'Sin balón' },
  en: { ritmo: 'Pace', disparo: 'Shooting', vision: 'Vision', regate: 'Dribbling', defensa: 'Defending', fisico: 'Physical', sin_balon: 'Off the ball' },
};

/** Abreviatura de 3 letras para la carta y nombre completo para lectores de pantalla. */
export const attributeShort: Record<Language, Record<CardAttribute, string>> = {
  es: { ritmo: 'RIT', disparo: 'DIS', vision: 'VIS', regate: 'REG', defensa: 'DEF', fisico: 'FÍS', sin_balon: 'SBL' },
  en: { ritmo: 'PAC', disparo: 'SHO', vision: 'VIS', regate: 'DRI', defensa: 'DEF', fisico: 'PHY', sin_balon: 'OTB' },
};

export const positionLabel: Record<Language, Record<Position, { short: string; long: string }>> = {
  es: {
    POR: { short: 'POR', long: 'Portero' }, LD: { short: 'LD', long: 'Lateral derecho' }, LI: { short: 'LI', long: 'Lateral izquierdo' },
    DFC: { short: 'DFC', long: 'Defensa central' }, MCD: { short: 'MCD', long: 'Medio de contención' }, MC: { short: 'MC', long: 'Mediocampista' },
    ED: { short: 'ED', long: 'Extremo derecho' }, EI: { short: 'EI', long: 'Extremo izquierdo' }, DC: { short: 'DC', long: 'Delantero centro' },
  },
  en: {
    POR: { short: 'GK', long: 'Goalkeeper' }, LD: { short: 'RB', long: 'Right back' }, LI: { short: 'LB', long: 'Left back' },
    DFC: { short: 'CB', long: 'Centre back' }, MCD: { short: 'DM', long: 'Defensive midfielder' }, MC: { short: 'CM', long: 'Central midfielder' },
    ED: { short: 'RW', long: 'Right winger' }, EI: { short: 'LW', long: 'Left winger' }, DC: { short: 'ST', long: 'Striker' },
  },
};

/** Ordinales: 1.º / 1st. */
export const ordinal = (n: number, lang: Language) => {
  if (lang === 'es') return `${n}.º`;
  const s = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th';
  return `${n}${s}`;
};

/** Reloj MM:SS desde t_s, igual que show_at. */
export const clock = (tS: number) => `${String(Math.floor(tS / 60)).padStart(2, '0')}:${String(tS % 60).padStart(2, '0')}`;

/** Formato de cifras por idioma (es-MX y en-GB usan punto decimal, igual que el motor). Solo formatea, nunca redondea distinto a `digits`. */
export const formatNumber = (value: number, lang: Language, digits = 0) =>
  new Intl.NumberFormat(lang === 'es' ? 'es-MX' : 'en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);

export const t = (template: string, vars: Record<string, string | number>) =>
  template.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
