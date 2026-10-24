/**
 * Baja-Insights · dirección visual "Litoral".
 * Espejo tipado de tokens.css para usar en JS (gráficos SVG, canvas, cálculos de layout).
 * En componentes con CSS usa siempre las variables `var(--bi-*)`, no estos valores directos.
 */

export const color = {
  ink: { 950: '#0c1418', 900: '#121e24', 800: '#1b2b33', 700: '#2a3f49', 600: '#3b5560', 500: '#5e7883', 300: '#a3b4bb', 100: '#dce4e7' },
  sand: { 50: '#fbf8f2', 100: '#f3ede2', 200: '#e7decf', 300: '#d4c8b4' },
  sol: { 300: '#ffb08f', 400: '#ff8a5c', 700: '#b4421c' },
  cortez: { 300: '#8fe3d8', 400: '#4fd1c1', 700: '#0b6e65' },
  alerta: { 400: '#ff7a7a', 700: '#b3261e' },
  team: {
    bahia: { solid: '#1f4e79', tint: '#86bdeb' },
    cardon: { solid: '#7a1f1f', tint: '#f2c14e' },
  },
  tier: { arena: '#c9b48a', coral: '#ff8a5c', perla: '#e6e1f5', ballena: '#6fb3dd' },
} as const;

/** Nombres de variables CSS semánticas, para `style={{ color: cssVar('text') }}`. */
export type SemanticToken =
  | 'bg' | 'surface' | 'surface-raised' | 'surface-overlay' | 'scrim'
  | 'text' | 'text-muted' | 'text-on-accent' | 'text-on-team'
  | 'line' | 'line-strong' | 'accent' | 'up' | 'verified' | 'live' | 'error' | 'focus'
  | 'team-home' | 'team-away' | 'team-home-solid' | 'team-away-solid';

export const cssVar = (token: SemanticToken) => `var(--bi-${token})`;

export type Theme = 'video' | 'dark' | 'light';

export const font = {
  display: '"Archivo", "Arial Narrow", "Roboto Condensed", system-ui, sans-serif',
  body: '"Archivo", system-ui, -apple-system, "Segoe UI", sans-serif',
  data: '"Spline Sans Mono", ui-monospace, "Cascadia Mono", Consolas, monospace',
  stretch: { condensed: '75%', normal: '100%' },
  weight: { regular: 400, medium: 500, bold: 700, black: 850 },
} as const;

/** Escala web en rem. */
export const textSize = {
  '2xs': '0.75rem', xs: '0.8125rem', sm: '0.875rem', md: '1rem', lg: '1.125rem',
  xl: '1.375rem', '2xl': '1.75rem', '3xl': '2.25rem', '4xl': '3rem',
} as const;

/** Escala de transmisión en px sobre lienzo 1920×1080. */
export const broadcastTextSize = { label: 22, body: 28, title: 36, headline: 48, hero: 72, score: 96 } as const;

export const space = { 0: 0, 1: 2, 2: 4, 3: 8, 4: 12, 5: 16, 6: 20, 7: 24, 8: 32, 9: 40, 10: 48, 11: 64 } as const;

export const radius = { xs: 2, sm: 4, md: 8, lg: 12, pill: 999, notch: 14, notchBroadcast: 24 } as const;

export const motion = {
  duration: { instant: 80, fast: 160, base: 240, slow: 400, reveal: 640 },
  easing: {
    out: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
    in: 'cubic-bezier(0.6, 0, 0.8, 0.4)',
    inOut: 'cubic-bezier(0.6, 0, 0.4, 1)',
  },
} as const;

export const breakpoint = { sm: 600, md: 900, lg: 1200 } as const;

/** Geometría de los slots del contrato sobre el lienzo de transmisión (px, 1920×1080, dentro de title-safe). */
export const broadcastSlots = {
  canvas: { width: 1920, height: 1080, safeX: 96, safeY: 54 },
  top_right: { x: 1344, y: 54, w: 480, h: 240 },
  side_panel: { x: 1344, y: 318, w: 480, h: 520 },
  lower_third: { x: 96, y: 760, w: 1100, h: 160 },
  bottom_bar: { x: 96, y: 954, w: 1728, h: 72 },
  center: { x: 480, y: 270, w: 960, h: 540 },
  full_screen: { x: 0, y: 0, w: 1920, h: 1080 },
} as const;

/**
 * Nivel visual de la carta según `overall` (dato del motor o de teams.json).
 * Es solo un umbral de presentación, no recalcula nada.
 */
export type CardTier = 'arena' | 'coral' | 'perla' | 'ballena';
export const cardTier = (overall: number): CardTier =>
  overall >= 80 ? 'ballena' : overall >= 70 ? 'perla' : overall >= 60 ? 'coral' : 'arena';
