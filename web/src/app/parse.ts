/** "63:09" → 3789, "63" → 3780, "3789" → 3789 (same rule as the engine's parse_clock). Invalid → 0. */
export function parseClockParam(value: string | null): number {
  if (!value) return 0;
  const text = value.trim().toLowerCase().replace(/s$/, '');
  const m = /^(\d{1,3}):([0-5]\d)$/.exec(text);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  if (!/^\d+$/.test(text)) return 0;
  const n = Number(text);
  return n <= 90 ? n * 60 : n;
}
