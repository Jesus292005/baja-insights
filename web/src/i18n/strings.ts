/**
 * Microcopy de la interfaz en español e inglés.
 * Solo textos de la UI. Los títulos y textos de cada gráfico vienen escritos por los agentes
 * en la orden (`title`, `text`) y la interfaz no los traduce ni los modifica.
 *
 * Variables entre llaves: {clock}, {player}, {from}, {to}, {ids}, {tools}, {query}, {seconds}.
 */
import type { CardAttribute, Language, OverlayType, Position } from '../contracts/overlay';

const es = {
  app: {
    name: 'Baja-Insights',
    tagline: 'El marcador no cuenta toda la historia.',
    fiction: 'Equipos, jugadores y datos ficticios.',
    skipToMatch: 'Saltar al partido',
    videoPlaceholder: 'Señal de video',
    matchPanels: 'Datos del partido',
    broadcastLink: 'Abrir overlay de transmisión',
    theme: 'Tema',
    themeLight: 'Claro',
    themeDark: 'Oscuro',
  },
  legend: {
    title: 'En el campo:',
    empty: 'Las jugadas aparecen en el campo cuando llega un momento con coordenadas.',
    pass: 'Pase',
    cross: 'Centro',
    shot: 'Remate',
    ball: 'Recorrido del balón',
    run: 'Desmarque sin balón',
    defender: 'Defensor arrastrado',
    recovery: 'Recuperación',
    duel: 'Duelo o entrada',
    pressure: 'Presión',
    separate: '{n} acciones de posesiones distintas, cada una con su minuto',
  },
  cinema: {
    link: 'Modo cine',
    badgeFan: 'Modo aficionado',
    badgeAnalyst: 'Modo analista',
    hint: 'H: atajos',
    helpTitle: 'Atajos del modo cine',
    keys: [
      ['Espacio', 'Reproducir o pausar'],
      ['M', 'Cambiar aficionado / analista'],
      ['L', 'Cambiar español / inglés'],
      ['N / P', 'Siguiente / anterior momento'],
      ['← / →', 'Retroceder / avanzar 10 s (Mayús: 60 s)'],
      ['B', 'Mostrar u ocultar el modo en pantalla'],
      ['F', 'Pantalla completa'],
      ['H', 'Mostrar u ocultar esta ayuda'],
    ],
  },
  source: {
    label: 'Fuente',
    replay: 'Repetición',
    live: 'En vivo',
    replayHint: 'El partido de demo desde el minuto que quieras.',
    liveHint: 'El stream en Azure, con un reloj compartido por todos.',
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
    ended: 'Partido terminado',
    retry: 'Reintentar',
    replay: 'Repetición',
    preMatch: 'El partido aún no empieza.',
    halfTime: 'Medio tiempo',
    fullTime: 'Final',
    asOf: 'Dato del {clock}',
    updated: 'Actualizado',
  },
  kicker: {
    mvp_update: 'MVP en vivo',
    duel_bar: 'Duelo de banda',
    standout_milestone: 'Hito',
    card_upgrade: 'Sube de nivel',
    goal_analysis: 'Cadena del gol',
    team_phase: 'Fase de juego',
    match_keys: 'Claves del partido',
    top3: 'Top 3 del partido',
    chat_answer: 'Pregúntale al partido',
  },
  mvp: {
    title: 'Carrera por el MVP',
    score: 'Puntaje MVP',
    leader: 'Líder',
    rankUp: 'Sube del {from} al {to}',
    newEntry: 'Entra al {to}',
    moves: 'Movimientos',
    finalTop: 'Top 3 final',
    empty: 'Aún no hay movimientos. La carrera aparece cuando alguien sube de puesto.',
    partial: 'Las órdenes aún no traen el ranking completo. Mostramos cada movimiento con su minuto.',
  },
  duel: {
    title: 'Duelo de banda',
    even: 'Parejo',
    ahead: 'Ventaja {player}',
    vsRole: 'vs. su rol',
    bar: 'Barra',
    legend: 'La barra compara a cada jugador con lo que se espera de su posición.',
    empty: 'Todavía no hay duelos directos. La barra se mueve con el primero.',
  },
  milestone: {
    label: 'Hito',
    expected: 'Esperado para su rol',
    aboveRole: 'sobre su rol',
    belowRole: 'bajo su rol',
  },
  stats: {
    recoveries: 'Recuperaciones',
    duels: 'Duelos ganados',
    progressive_passes: 'Pases progresivos',
    key_passes: 'Pases clave',
    vs_role: 'Frente a su rol',
    mvp_rank: 'Puesto MVP',
    possession: 'Posesión',
    pass_accuracy: 'Precisión de pase',
    passes_per_min: 'Pases por minuto',
    def_height: 'Altura de acciones defensivas',
    score: 'Puntaje',
    xg: 'xG',
  },
  card: {
    levelUp: 'Sube de nivel',
    overall: 'Media',
    base: 'Carta inicial',
    noChanges: 'Sin cambios todavía.',
    overallPending: 'Media sin dato',
    overallUp: 'Media, antes {from}',
    follow: 'Seguir a',
    title: 'Tu jugador',
    changes: 'Cambios en el partido',
    tier: { arena: 'Arena', coral: 'Coral', perla: 'Perla', ballena: 'Ballena' },
  },
  goal: {
    title: 'Cadena del gol',
    credit: 'Crédito',
    invisible: 'Asistencia invisible',
    invisibleHint: 'Influyó en el gol sin tocar el balón.',
    spaceOpened: '{meters} m abiertos',
    empty: 'Todavía no hay goles.',
  },
  phase: { control: 'Control', pressure_shift: 'Cambio de presión' },
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
    label: 'Tu pregunta',
    send: 'Preguntar',
    sending: 'Consultando los datos del partido…',
    answeredWith: 'Respondido con',
    notTracked: 'Ese dato no se mide en este partido.',
    notFound: 'No encontramos ese nombre en este partido. Revísalo.',
    noPrediction: 'Sin predicciones: solo lo que ya pasó.',
    error: 'No pudimos consultar el partido. Tu pregunta sigue aquí, inténtalo de nuevo.',
    offline: 'El chat vuelve cuando se recupere la conexión.',
    rateLimited: 'Llegaron muchas preguntas en este minuto. Tu pregunta sigue aquí; inténtalo en unos segundos.',
    timeout: 'El partido tardó demasiado en responder. Tu pregunta sigue aquí, inténtalo de nuevo.',
    showOnScreen: 'Mostrar en pantalla',
    showing: 'Enviando a pantalla…',
    shown: 'En pantalla',
    showFailed: 'No se pudo mostrar. Reintentar',
    unavailable: 'El chat todavía no está conectado con el agente. Cuando lo esté, responderá solo con datos del partido.',
    you: 'Tú',
    match: 'El partido',
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
    open: 'Ver la tarjeta de este momento',
    close: 'Ocultar la tarjeta',
  },
  halftime: {
    title: 'Medio tiempo',
    swap: 'Los equipos cambian de lado',
    attacks: 'En el segundo tiempo cada equipo ataca hacia su flecha.',
  },
  pitch: {
    ends: 'Cancha, tiempo {half}: portería de {left} a la izquierda y de {right} a la derecha.',
  },
  band: {
    label: 'Tarjetas del partido',
    empty: 'Las tarjetas aparecen aquí cuando pasa algo en el campo.',
  },
  replay: {
    label: 'Repetición del partido',
    play: 'Reproducir',
    pause: 'Pausar',
    speed: 'Velocidad',
    seek: 'Momento del partido',
    skip: 'Acelerar solo entre momentos',
    restart: 'Desde el inicio',
  },
  noData: { short: '—', a11y: 'Sin dato' },
  units: { minute: 'min', second: 's', meters: 'm', pct: '%' },
} as const;

type Shape<T> = {
  [K in keyof T]: T[K] extends string
    ? string
    : T[K] extends readonly string[]
      ? readonly string[]
      : T[K] extends readonly (readonly string[])[]
        ? readonly (readonly [string, string])[]
        : Shape<T[K]>;
};

const en: Shape<typeof es> = {
  app: {
    name: 'Baja-Insights',
    tagline: "The scoreline doesn't tell the whole story.",
    fiction: 'Fictional teams, players and data.',
    skipToMatch: 'Skip to the match',
    videoPlaceholder: 'Video feed',
    matchPanels: 'Match data',
    broadcastLink: 'Open broadcast overlay',
    theme: 'Theme',
    themeLight: 'Light',
    themeDark: 'Dark',
  },
  legend: {
    title: 'On the pitch:',
    empty: 'Plays show up on the pitch when a moment with coordinates arrives.',
    pass: 'Pass',
    cross: 'Cross',
    shot: 'Shot',
    ball: 'Ball path',
    run: 'Off-ball run',
    defender: 'Dragged defender',
    recovery: 'Recovery',
    duel: 'Duel or tackle',
    pressure: 'Pressure',
    separate: '{n} actions from separate possessions, each with its minute',
  },
  cinema: {
    link: 'Cinema mode',
    badgeFan: 'Fan mode',
    badgeAnalyst: 'Analyst mode',
    hint: 'H: shortcuts',
    helpTitle: 'Cinema mode shortcuts',
    keys: [
      ['Space', 'Play or pause'],
      ['M', 'Switch fan / analyst'],
      ['L', 'Switch Spanish / English'],
      ['N / P', 'Next / previous moment'],
      ['← / →', 'Back / forward 10 s (Shift: 60 s)'],
      ['B', 'Show or hide the mode on screen'],
      ['F', 'Full screen'],
      ['H', 'Show or hide this help'],
    ],
  },
  source: {
    label: 'Source',
    replay: 'Replay',
    live: 'Live',
    replayHint: 'The demo match from any minute you like.',
    liveHint: 'The stream on Azure, with one clock shared by everyone.',
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
    offlineBody: 'What you see is the last confirmed data, from {clock}.',
    ended: 'Match over',
    retry: 'Try again',
    replay: 'Replay',
    preMatch: "The match hasn't started yet.",
    halfTime: 'Half-time',
    fullTime: 'Full-time',
    asOf: 'As of {clock}',
    updated: 'Updated',
  },
  kicker: {
    mvp_update: 'Live MVP',
    duel_bar: 'Flank duel',
    standout_milestone: 'Milestone',
    card_upgrade: 'Level up',
    goal_analysis: 'Goal chain',
    team_phase: 'Phase of play',
    match_keys: 'Match keys',
    top3: 'Match top 3',
    chat_answer: 'Ask the match',
  },
  mvp: {
    title: 'MVP race',
    score: 'MVP score',
    leader: 'Leader',
    rankUp: 'Up from {from} to {to}',
    newEntry: 'In at {to}',
    moves: 'Moves',
    finalTop: 'Final top 3',
    empty: 'No moves yet. The race shows up when someone climbs.',
    partial: "The orders don't carry the full ranking yet. Each move is shown with its minute.",
  },
  duel: {
    title: 'Flank duel',
    even: 'Even',
    ahead: '{player} ahead',
    vsRole: 'vs. role',
    bar: 'Bar',
    legend: "The bar compares each player with what's expected for their position.",
    empty: 'No head-to-head duels yet. The bar moves after the first one.',
  },
  milestone: {
    label: 'Milestone',
    expected: 'Expected for the role',
    aboveRole: 'above role',
    belowRole: 'below role',
  },
  stats: {
    recoveries: 'Recoveries',
    duels: 'Duels won',
    progressive_passes: 'Progressive passes',
    key_passes: 'Key passes',
    vs_role: 'Against role',
    mvp_rank: 'MVP rank',
    possession: 'Possession',
    pass_accuracy: 'Pass accuracy',
    passes_per_min: 'Passes per minute',
    def_height: 'Defensive action height',
    score: 'Score',
    xg: 'xG',
  },
  card: {
    levelUp: 'Level up',
    overall: 'Overall',
    base: 'Starting card',
    noChanges: 'No changes yet.',
    overallPending: 'Overall not available',
    overallUp: 'Overall, was {from}',
    follow: 'Follow',
    title: 'Your player',
    changes: 'Changes this match',
    tier: { arena: 'Sand', coral: 'Coral', perla: 'Pearl', ballena: 'Whale' },
  },
  goal: {
    title: 'Goal chain',
    credit: 'Credit',
    invisible: 'Invisible assist',
    invisibleHint: 'Shaped the goal without touching the ball.',
    spaceOpened: '{meters} m opened',
    empty: 'No goals yet.',
  },
  phase: { control: 'Control', pressure_shift: 'Pressure shift' },
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
    label: 'Your question',
    send: 'Ask',
    sending: 'Checking the match data…',
    answeredWith: 'Answered with',
    notTracked: "That isn't tracked in this match.",
    notFound: "We couldn't find that name in this match. Check it.",
    noPrediction: 'No predictions, only what has happened.',
    error: "We couldn't reach the match data. Your question is still here, try again.",
    offline: 'Chat comes back when the connection does.',
    rateLimited: 'Too many questions this minute. Your question is still here; try again in a few seconds.',
    timeout: 'The match took too long to answer. Your question is still here, try again.',
    showOnScreen: 'Show on screen',
    showing: 'Sending to screen…',
    shown: 'On screen',
    showFailed: "Couldn't show it. Try again",
    unavailable: "Chat isn't connected to the agent yet. Once it is, it will answer only from match data.",
    you: 'You',
    match: 'The match',
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
    open: "Show this moment's card",
    close: 'Hide the card',
  },
  halftime: {
    title: 'Half-time',
    swap: 'Teams switch ends',
    attacks: 'In the second half each team attacks towards its arrow.',
  },
  pitch: {
    ends: 'Pitch, half {half}: {left} goal on the left, {right} goal on the right.',
  },
  band: {
    label: 'Match cards',
    empty: 'Cards show up here when something happens on the pitch.',
  },
  replay: {
    label: 'Match replay',
    play: 'Play',
    pause: 'Pause',
    speed: 'Speed',
    seek: 'Match moment',
    skip: 'Speed up only between moments',
    restart: 'From the start',
  },
  noData: { short: '—', a11y: 'No data' },
  units: { minute: 'min', second: 's', meters: 'm', pct: '%' },
};

export const strings = { es, en } as const;
export type Strings = Shape<typeof es>;

export type KickerKey = OverlayType;

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

/** Reloj MM:SS desde segundos del partido, igual que show_at. */
export const clock = (tS: number) => {
  const s = Math.max(0, Math.floor(tS));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
};

/** Formato de cifras por idioma (es-MX y en-GB usan punto decimal, igual que el motor). Solo formatea. */
export const formatNumber = (value: number, lang: Language, digits = 0) =>
  new Intl.NumberFormat(lang === 'es' ? 'es-MX' : 'en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);

/**
 * Cifra del motor tal como llegó: nunca quita decimales (0.44 no se vuelve 0.4).
 * `minDigits` solo agrega ceros a la derecha para alinear (0.1 → 0.10).
 */
export const asSent = (value: number, lang: Language, minDigits = 0) =>
  new Intl.NumberFormat(lang === 'es' ? 'es-MX' : 'en-GB', {
    minimumFractionDigits: minDigits,
    maximumFractionDigits: Math.max(minDigits, 3),
  }).format(value);

/** Número con signo para diferencias que ya vienen calculadas: +0.60, −0.40. */
export const signed = (value: number, lang: Language, minDigits = 2) =>
  `${value > 0 ? '+' : value < 0 ? '−' : ''}${asSent(Math.abs(value), lang, minDigits)}`;

/** Fracción del motor como porcentaje con signo: 0.89 → +89%. Solo cambia la escala. */
export const signedPct = (fraction: number, lang: Language) => `${signed(fraction * 100, lang, 0)}%`;

/** Fracción como porcentaje sin signo: 0.35 → 35. */
export const pct = (fraction: number, lang: Language) => asSent(fraction * 100, lang);

export const t = (template: string, vars: Record<string, string | number>) =>
  template.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));

/** Apellido para textos cortos: "D. Verdugo" → "Verdugo". */
export const surname = (name: string) => name.replace(/^[A-ZÁÉÍÓÚÑ]\.\s*/u, '');
