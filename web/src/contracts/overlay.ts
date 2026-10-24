/**
 * Tipos de las órdenes de gráfico, espejo de contracts/overlay.schema.json (contrato v1).
 * Las formas de `data` salen de mocks/overlays_sample.json y data/m001/overlays.json.
 *
 * Los campos marcados con `@proposed v1.1` están en el contrato v1.1 aprobado (docs/cambios-contrato-v1.1.md),
 * pero el motor y los agentes todavía no los producen.
 * La UI debe funcionar sin ellos (estado vacío honesto).
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
  /** @proposed v1.1 — hoy solo existe en el insight. Sin él, la UI no muestra la media. */
  overall_from?: number;
  /** @proposed v1.1 */
  overall_to?: number;
  /** @proposed v1.1 — motivo del motor, para modo analista. */
  reason?: string;
}

export interface RankingEntry { rank: number; player: string; team: string; position: Position; mvp_score: number }

export interface MvpUpdateData {
  rank: number;
  previous_rank?: number;
  mvp_score: number;
  /** @proposed v1.1 — foto del top 5 en ese instante (misma forma que get_mvp_ranking). Necesaria para la carrera. */
  ranking?: RankingEntry[];
}

export interface DuelBarData {
  /** Siempre el jugador local. */
  player_a: string;
  player_b: string;
  /** −1 gana player_b, 0 parejo, +1 gana player_a. bar = (a_vs_role − b_vs_role) / 2 */
  bar: number;
}

export interface ChainLink { event_id: number; player: string; action: string; credit: number; t_s: number }
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
  /** @proposed v1.1 — eslabones completos (acción, tiempo, evidencia) para modo analista. */
  chain_detail?: ChainLink[];
}

/** Nombre del jugador de la asistencia invisible, venga como objeto (v1.1) o como texto (v1). */
export const invisibleAssistPlayer = (v: GoalAnalysisData['invisible_assist']) =>
  v == null ? null : typeof v === 'string' ? v : v.player;

export interface TeamPhaseData {
  label: 'control' | 'pressure_shift';
  possession_pct?: number;
  pass_accuracy_pct?: number;
  passes_per_min?: number;
  /** Altura media de las acciones defensivas, en metros desde su portería. */
  def_action_height_m?: number;
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

/** @proposed v1.1 — `data` obligatorio de chat_answer. */
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
  /** @proposed v1.1 — event_id que respaldan la orden (hoy solo están en el insight). */
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
 * @proposed v1.1 — contracts/stream.schema.json. `clock` es el latido (uno por segundo);
 * 3 s sin él = reconectando. Al reconectar, la UI manda `subscribe` con su último t_s.
 */
export type StreamClientMessage = { kind: 'subscribe'; match_id: string; from_t_s: number };

export type StreamServerMessage =
  | { kind: 'overlay'; order: OverlayOrder }
  | { kind: 'clock'; match_id: string; t_s: number; period: 1 | 2; phase: 'pre' | 'live' | 'half_time' | 'full_time'; speed?: number }
  | { kind: 'state'; match_id: string; t_s: number; home: string; away: string; scoreline: Scoreline }
  | { kind: 'error'; code: 'match_not_found' | 'stream_ended' | 'server_error'; detail?: string };

export const HEARTBEAT_TIMEOUT_MS = 3000;

export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'offline' | 'replay';

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
