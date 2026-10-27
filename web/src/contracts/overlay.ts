/**
 * Tipos de las órdenes de gráfico, espejo de contracts/overlay.schema.json (contrato v1.1),
 * más los mensajes de contracts/stream.schema.json y contracts/chat.schema.json.
 * Las formas de `data` salen de mocks/overlays_sample.json y data/m001/overlays.json.
 *
 * Los campos marcados `v1.1` son opcionales en el esquema: las órdenes v1 no los traen y la UI
 * debe funcionar sin ellos (estado vacío honesto).
 */

export type Mode = 'fan' | 'analyst';
export type Language = 'es' | 'en';
export type Slot = 'top_right' | 'lower_third' | 'side_panel' | 'bottom_bar' | 'center' | 'full_screen';
export type Position = 'POR' | 'LD' | 'LI' | 'DFC' | 'MCD' | 'MC' | 'ED' | 'EI' | 'DC';
export type CardAttribute = 'ritmo' | 'disparo' | 'vision' | 'regate' | 'defensa' | 'fisico' | 'sin_balon';
export type OverlayType =
  | 'mvp_update' | 'duel_bar' | 'standout_milestone' | 'card_upgrade' | 'goal_analysis'
  | 'team_phase' | 'match_keys' | 'top3' | 'chat_answer';

export interface Scoreline { home: number; away: number }
export interface HomeAway<T = number> { home: T; away: T }

/** `card` de la orden: el atributo que sube. */
export interface OverlayCard {
  player: string;
  team: string;
  position: Position;
  attribute: CardAttribute;
  from: number;
  to: number;
  delta: number;
  /** v1.1 — media del motor antes del cambio. Sin ella, la UI no muestra la media. */
  overall_from?: number;
  /** v1.1 */
  overall_to?: number;
  /** v1.1 — motivo del motor en español. Respaldo cuando falta `reason_code`. */
  reason?: string;
  /** v1.1 — qué dice el motivo, para escribirlo en cada idioma (contracts/README.md). */
  reason_code?: ReasonCode;
  /** v1.1 — números y nombres del motivo, según el código. */
  reason_params?: Record<string, number | string | boolean | null>;
}

export type ReasonCode =
  | 'line_breaking_pass' | 'opp_half_recoveries' | 'shot_speed' | 'duel_streak' | 'run_speed'
  | 'dribbles' | 'run_ended_in_shot' | 'run_opened_goal' | 'standout_defensive' | 'standout_creative';

export interface RankingEntry { rank: number; player: string; team: string; position: Position; mvp_score: number }

export interface MvpUpdateData {
  rank: number;
  previous_rank?: number;
  mvp_score: number;
  /** v1.1 — foto del top 5 en ese instante (misma forma que get_mvp_ranking). Necesaria para la carrera. */
  ranking?: RankingEntry[];
}

export interface DuelBarData {
  /** Siempre el jugador local. */
  player_a: string;
  player_b: string;
  /** −1 gana player_b, 0 parejo, +1 gana player_a. bar = (a_vs_role − b_vs_role) / 2 */
  bar: number;
}

export type ChainLinkType = 'pass' | 'shot' | 'tackle' | 'recovery' | 'duel' | 'pressure' | 'foul' | 'off_ball_run';

export interface ChainLink {
  event_id: number;
  player: string;
  /** Etiqueta en español del motor. Respaldo cuando falta `type`. */
  action: string;
  credit: number;
  t_s: number;
  /** v1.1 — tipo del evento, para escribir la acción en cada idioma. */
  type?: ChainLinkType;
  /** v1.1 — líneas rotas por el pase, 0 si no aplica. */
  lines_broken?: number;
  /** v1.1 — solo en pases que son centros. */
  cross?: boolean;
  /** v1.1 — dónde ocurrió la acción, [x, y] en metros (origen abajo a la izquierda, 105 × 68). */
  start?: PitchPoint | null;
  /** v1.1 — a dónde fue el pase, el tiro o el desmarque. null en recuperaciones. */
  end?: PitchPoint | null;
  /** v1.1 — solo en desmarques: el defensor arrastrado. */
  dragged_defender?: string | null;
  /** v1.1 — solo en desmarques guionizados: dónde estaba el defensor y a dónde lo llevó el desmarque. */
  dragged_defender_start?: PitchPoint | null;
  dragged_defender_end?: PitchPoint | null;
}

/** Punto del campo en metros: x de 0 a 105 (Bahía ataca hacia 105), y de 0 a 68 desde abajo. */
export type PitchPoint = [number, number];
export interface InvisibleAssistDetail { player: string; dragged_defender: string | null; space_opened_m: number | null; touched_ball: boolean }

export interface GoalAnalysisData {
  /** Nombres en orden temporal. */
  chain: string[];
  /** Crédito por eslabón, mismo índice que `chain`, suma 1. */
  credit: number[];
  /** v1.1: objeto (lo que ya emiten los agentes). El texto con solo el nombre es v1 y queda obsoleto. */
  invisible_assist?: InvisibleAssistDetail | string | null;
  scoreline?: Scoreline;
  xg?: number;
  /** v1.1 — eslabones completos (acción, tiempo, evidencia) para modo analista. */
  chain_detail?: ChainLink[];
}

/** Nombre del jugador de la asistencia invisible, venga como objeto (v1.1) o como texto (v1). */
export const invisibleAssistPlayer = (v: GoalAnalysisData['invisible_assist']) =>
  v == null ? null : typeof v === 'string' ? v : v.player;

/**
 * Las métricas llegan como número (mock) o por equipo (salida real de los agentes).
 * La orden no dice a qué equipo se refiere un número suelto, así que la UI no lo atribuye.
 */
export interface TeamPhaseData {
  label: 'control' | 'pressure_shift';
  possession_pct?: number | HomeAway;
  pass_accuracy_pct?: number | HomeAway;
  passes_per_min?: number | HomeAway;
  /** Altura media de las acciones defensivas, en metros desde su portería. */
  def_action_height_m?: number | HomeAway;
}

export interface StandoutMilestoneData {
  recoveries?: number;
  duels_won?: number;
  duels_total?: number;
  progressive_passes?: number;
  key_passes?: number;
  mvp_rank?: number;
  vs_role?: number;
}

export interface MatchKeysData {
  xg: HomeAway;
  possession_pct: HomeAway;
  scoreline?: Scoreline;
}

export interface Top3Card { rank: 1 | 2 | 3; player: string; mvp_score: number; team?: string; position?: Position }
export interface Top3Data { cards: Top3Card[]; final_scoreline?: Scoreline }

export type ChatTool =
  | 'get_match_state' | 'get_mvp_ranking' | 'get_player_summary' | 'get_duel' | 'get_team_phase' | 'get_goal_chain';

/** v1.1 — `data` obligatorio de chat_answer. */
export interface ChatAnswerData {
  question: string;
  status: 'answered' | 'not_tracked' | 'not_found' | 'no_prediction';
  /** Funciones del motor que respaldan la respuesta, p. ej. ['get_duel']. */
  tools: ChatTool[];
  evidence?: number[];
}

interface OverlayBase<T extends OverlayType, D> {
  overlay_id: string;
  match_id: string;
  /** null en los fotogramas de animación de la barra de duelo. */
  source_insight: string | null;
  period: 1 | 2;
  show_at: string;
  show_at_s: number;
  duration_s: number;
  slot: Slot;
  mode: Mode | 'all';
  language: Language | 'all';
  type: T;
  title: string | null;
  text: string | null;
  card?: OverlayCard | null;
  data?: D | null;
  /** v1.1 — event_id que respaldan la orden. Los fotogramas de la barra de duelo no lo traen. */
  evidence?: number[];
}

export type MvpUpdateOrder = OverlayBase<'mvp_update', MvpUpdateData> & { data: MvpUpdateData };
export type DuelBarOrder = OverlayBase<'duel_bar', DuelBarData> & { data: DuelBarData };
export type StandoutMilestoneOrder = OverlayBase<'standout_milestone', StandoutMilestoneData>;
export type CardUpgradeOrder = OverlayBase<'card_upgrade', never> & { card: OverlayCard };
export type GoalAnalysisOrder = OverlayBase<'goal_analysis', GoalAnalysisData> & { data: GoalAnalysisData };
export type TeamPhaseOrder = OverlayBase<'team_phase', TeamPhaseData>;
export type MatchKeysOrder = OverlayBase<'match_keys', MatchKeysData>;
export type Top3Order = OverlayBase<'top3', Top3Data> & { data: Top3Data };
export type ChatAnswerOrder = OverlayBase<'chat_answer', ChatAnswerData>;

export type OverlayOrder =
  | MvpUpdateOrder | DuelBarOrder | StandoutMilestoneOrder | CardUpgradeOrder | GoalAnalysisOrder
  | TeamPhaseOrder | MatchKeysOrder | Top3Order | ChatAnswerOrder;

/** Una orden aplica al espectador si coincide su modo e idioma, o si es `all`. */
export const appliesTo = (o: OverlayOrder, mode: Mode, language: Language) =>
  (o.mode === 'all' || o.mode === mode) && (o.language === 'all' || o.language === language);

/** Es un fotograma de animación de la barra de duelo, sin texto. */
export const isDuelFrame = (o: OverlayOrder): o is DuelBarOrder => o.type === 'duel_bar' && o.source_insight === null;

/* ---------- Stream ---------- */

/**
 * v1.1 — contracts/stream.schema.json. `clock` es el latido (uno por segundo);
 * 3 s sin él = reconectando. Al reconectar, la UI manda `subscribe` con su último t_s.
 */
export type StreamClientMessage = { kind: 'subscribe'; match_id: string; from_t_s: number };

export type StreamServerMessage =
  | { kind: 'overlay'; order: OverlayOrder }
  | { kind: 'clock'; match_id: string; t_s: number; period: 1 | 2; phase: 'pre' | 'live' | 'half_time' | 'full_time'; speed?: number }
  | { kind: 'state'; match_id: string; t_s: number; home: string; away: string; scoreline: Scoreline }
  | { kind: 'error'; code: 'match_not_found' | 'stream_ended' | 'server_error'; detail?: string };

export const HEARTBEAT_TIMEOUT_MS = 3000;

/** `ended`: the server sent `stream_ended`. The match is over, the heartbeat goes on: not a failure. */
export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'offline' | 'ended' | 'replay';

/* ---------- Pregúntale al partido: POST /api/ask (contracts/chat.schema.json, v1.1) ---------- */

export interface ChatRequest {
  match_id: string;
  question: string;
  /** 'MM:SS' o segundos del partido. */
  at: string | number;
  mode: Mode;
  language: Language;
  favorite_team?: string | null;
  /** Hasta 6 turnos, el más antiguo primero. */
  history?: { role: 'user' | 'match'; text: string }[];
}

export type ChatResponse = {
  match_id: string;
  question: string;
  at_s: number;
  tools: ChatTool[];
  evidence?: number[];
} & (
  | { status: 'answered' | 'not_tracked' | 'not_found' | 'no_prediction'; answer: string }
  | { status: 'error'; answer: null; error: 'timeout' | 'engine_unavailable' | 'agent_failed' }
);
