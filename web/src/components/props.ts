/**
 * Props de los componentes de Baja-Insights, derivadas de contracts/overlay.schema.json.
 *
 * Regla de oro: ningún componente calcula cifras. Reciben números ya hechos por el motor
 * (vía la orden de gráfico) y solo los formatean. Si falta un dato, se muestra `EmptyState`
 * o el guion largo "—" con su etiqueta accesible, nunca un valor estimado.
 */
import type {
  CardAttribute, ChainLink, ConnectionStatus, DuelBarOrder, GoalAnalysisData, Language, MatchKeysData,
  Mode, MvpUpdateOrder, OverlayCard, OverlayOrder, Position, RankingEntry, Scoreline, Slot,
  StandoutMilestoneOrder, TeamPhaseData, Top3Card,
} from '../contracts/overlay';
import type { CardTier, Theme } from '../design/tokens';

/* ---------- Tipos de apoyo ---------- */

/** Estado de cualquier dato que llega por stream. */
export type Live<T> =
  | { status: 'loading' }
  | { status: 'empty' }
  | { status: 'ready'; value: T; /** segundo del partido del dato */ asOfS: number; /** true mientras se reconecta */ stale?: boolean }
  | { status: 'error'; message?: string };

/** Equipo, tomado de mocks/teams.json. */
export interface TeamRef { name: string; short: string; colors: [string, string] }

/** Jugador, tomado de mocks/teams.json. */
export interface PlayerRef { name: string; team: string; position: Position; number?: number }

export type Variant = 'web' | 'broadcast';

interface Localized { mode: Mode; language: Language }

/** Título y texto tal cual vienen de la orden (los escribe el agente, la UI no los cambia). */
interface OrderCopy { title: string | null; text: string | null }

/* ---------- Estructura ---------- */

export interface AppShellProps {
  variant: Variant;
  theme: Theme;
  children: React.ReactNode;
}

/** Marcador + reloj. Solo muestra lo que llega en el stream (mensaje `state` / `clock`). */
export interface MatchBugProps {
  home: TeamRef;
  away: TeamRef;
  scoreline: Scoreline | null;
  clockS: number | null;
  period: 1 | 2 | null;
  phase: 'pre' | 'live' | 'half_time' | 'full_time' | null;
  connection: ConnectionStatus;
  variant: Variant;
}

export interface ConnectionBannerProps {
  status: ConnectionStatus;
  /** Último segundo con datos confirmados, para "Mostrando datos hasta el 63:09". */
  lastDataS: number | null;
  /** Intento actual y espera en segundos, en reconexión. */
  attempt?: number;
  retryInS?: number;
  onRetry: () => void;
  language: Language;
}

export interface ModeToggleProps { value: Mode; onChange: (mode: Mode) => void; language: Language }
export interface LanguageToggleProps { value: Language; onChange: (language: Language) => void }

/* ---------- Escenario de órdenes ---------- */

/**
 * Reproduce las órdenes: muestra cada una cuando clockS ≥ show_at_s durante duration_s,
 * filtrada con appliesTo(mode, language). Una orden por slot; la siguiente espera en cola.
 * Prioridad de slots: full_screen > center > resto. `center` pausa side_panel y lower_third.
 */
export interface OverlayStageProps extends Localized {
  orders: OverlayOrder[];
  clockS: number;
  variant: Variant;
  /** Solo web: escala del lienzo 1920×1080 al contenedor. */
  fit?: 'contain' | 'width';
  /** Anuncia en aria-live el título y texto de cada orden nueva (solo web). */
  announce?: boolean;
  onOrderShown?: (order: OverlayOrder) => void;
}

export interface SlotRegionProps {
  slot: Slot;
  order: OverlayOrder | null;
  /** Órdenes esperando turno en este slot. */
  queued: number;
  variant: Variant;
  children?: React.ReactNode;
}

/** Marco común de todo gráfico: corte litoral, título, texto y línea de marea. */
export interface OverlayPanelProps extends OrderCopy {
  slot: Slot;
  variant: Variant;
  mode: Mode;
  /** Equipo protagonista para la franja de color (con su nombre, nunca solo color). */
  team?: TeamRef;
  /** Línea de marea: se vacía en duration_s. */
  durationS: number;
  elapsedS: number;
  evidence?: number[];
  children?: React.ReactNode;
}

export interface TideLineProps { durationS: number; elapsedS: number; paused?: boolean }

/* ---------- 1. Carrera MVP ---------- */

/** Aviso puntual de subida (orden mvp_update, slot top_right). */
export interface MvpUpdateGraphicProps extends Localized {
  order: MvpUpdateOrder;
  team?: TeamRef;
}

/**
 * Ranking persistente del rail. Necesita `data.ranking` (propuesta v1.1).
 * Sin ranking completo muestra solo el último movimiento y el líder conocido, con su minuto.
 */
export interface MvpRaceProps extends Localized {
  ranking: Live<RankingEntry[]>;
  /** Puesto anterior por jugador, del último mvp_update (previous_rank). */
  previousRanks?: Record<string, number>;
  /** Jugador que el espectador sigue. */
  followedPlayer?: string;
  /** fan: top 3; analyst: top 5 con puntaje. */
  size?: 3 | 5;
  teams: TeamRef[];
}

export interface RankChangeProps { from: number | null; to: number; language: Language }

/* ---------- 2. Duelo de banda ---------- */

export interface DuelBarProps extends Localized, OrderCopy {
  playerA: PlayerRef;
  playerB: PlayerRef;
  /** −1..1 del motor. null = aún no hay duelos directos. */
  bar: number | null;
  /** true en fotogramas de animación (source_insight null): sin texto, solo mueve la barra. */
  frame: boolean;
  /** Solo analista y solo si vienen en el texto o una extensión del contrato. */
  aVsRole?: number;
  bVsRole?: number;
  variant: Variant;
  stale?: boolean;
}

export const duelBarFromOrder = (o: DuelBarOrder) => ({ bar: o.data.bar, frame: o.source_insight === null });

/* ---------- 3. Hitos ---------- */

export interface StandoutMilestoneProps extends Localized {
  order: StandoutMilestoneOrder;
  player: PlayerRef;
  team: TeamRef;
}

/** Cifra con su referencia de rol, ambas ya calculadas por el motor. */
export interface StatWithBaselineProps {
  label: string;
  value: number | null;
  /** Lo esperado para el rol, si el motor lo manda. */
  expected?: number | null;
  /** Diferencia relativa ya calculada (vs_role), si viene. */
  vsRole?: number | null;
  format?: 'int' | 'dec1' | 'dec2' | 'pct';
}

/* ---------- 4. Cadena de gol ---------- */

export interface GoalChainProps extends Localized, OrderCopy {
  data: GoalAnalysisData;
  /** Eslabones completos si llega chain_detail (v1.1); si no, solo nombres y crédito. */
  detail?: ChainLink[];
  scoringTeam?: TeamRef;
  variant: Variant;
}

/* ---------- 5. Cartas ---------- */

export interface CardChange { attribute: CardAttribute; from: number; to: number; delta: number; atS: number; reason?: string }

export interface PlayerCardProps extends Localized {
  player: PlayerRef;
  team: TeamRef;
  /** Atributos base de teams.json, sustituidos por el último `to` de cada orden con `card`. */
  attributes: Record<CardAttribute, number>;
  /** overall del motor (overall_to). null si el contrato aún no lo manda en la orden. */
  overall: number | null;
  tier: CardTier;
  changes: CardChange[];
  /** Atributo que se anima al subir. */
  highlight?: CardAttribute;
  size: 'sm' | 'md' | 'lg';
  state: 'base' | 'leveling' | 'leveled';
}

/** Aviso de subida (orden card_upgrade, slot lower_third). */
export interface CardUpgradeToastProps extends Localized, OrderCopy {
  card: OverlayCard;
  team?: TeamRef;
  variant: Variant;
}

/* ---------- Otros gráficos del contrato ---------- */

export interface TeamPhasePanelProps extends Localized, OrderCopy {
  data: TeamPhaseData;
  team?: TeamRef;
  variant: Variant;
}

export interface MatchKeysPanelProps extends Localized, OrderCopy {
  data: MatchKeysData;
  home: TeamRef;
  away: TeamRef;
  variant: Variant;
}

export interface Top3RevealProps extends Localized, OrderCopy {
  cards: Top3Card[];
  finalScoreline?: Scoreline;
  teams: TeamRef[];
  variant: Variant;
}

/* ---------- 6. Pregúntale al partido ---------- */

export interface ChatMessage {
  id: string;
  role: 'user' | 'match';
  text: string;
  /** Segundo del partido en que se preguntó. */
  atS: number;
  status?: 'answered' | 'not_tracked' | 'not_found' | 'no_prediction' | 'error';
  tools?: string[];
  evidence?: number[];
}

export interface AskTheMatchProps extends Localized {
  messages: ChatMessage[];
  status: 'idle' | 'sending' | 'error' | 'offline';
  /** Sugerencias con nombres sacados de los datos (p. ej. el líder del MVP), nunca inventados. */
  suggestions: string[];
  onAsk: (question: string) => void;
  onRetry: () => void;
  /** Panel lateral en escritorio, hoja inferior en móvil. */
  presentation: 'rail' | 'sheet';
}

export interface EvidenceChipsProps { eventIds: number[]; tools?: string[]; language: Language }

/* ---------- 7 y 8. Utilidades ---------- */

export interface MomentTimelineProps extends Localized {
  /** Órdenes que ya se mostraron, más recientes arriba. */
  shown: OverlayOrder[];
  clockS: number;
  onSelect: (order: OverlayOrder) => void;
}

export interface EmptyStateProps { title: string; body?: string; action?: { label: string; onClick: () => void } }

export interface SkeletonProps { shape: 'line' | 'block' | 'card' | 'bar' | 'row'; width?: number | string; height?: number | string; lines?: number }
