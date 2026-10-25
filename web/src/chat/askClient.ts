import type { ChatAnswerOrder, ChatRequest, ChatResponse, Language, Mode } from '../contracts/overlay';

/**
 * Client for the chat service (agents/baja_agents/server.py):
 *   POST /api/ask           question → answer, contracts/chat.schema.json
 *   POST /api/chat-overlay  answer → chat_answer graphics order, no model call
 *
 * The /api/ask URL comes from ../app/endpoints (deployed service, or VITE_ASK_URL). Without it
 * the chat says it is not connected instead of making anything up.
 */
import { askUrl } from '../app/endpoints';

export { askUrl };

/** Why a call gave no usable answer. Each one has its own message in the UI. */
export type ChatFailure = 'not_configured' | 'rate_limited' | 'timeout' | 'unavailable' | 'failed';

export type AskResult = { ok: true; response: Exclude<ChatResponse, { status: 'error' }> } | { ok: false; reason: ChatFailure };
export type OverlayResult = { ok: true; order: ChatAnswerOrder } | { ok: false; reason: ChatFailure };

const STATUSES = new Set(['answered', 'not_tracked', 'not_found', 'no_prediction', 'error']);

async function post(url: string, body: unknown, timeoutMs: number): Promise<{ ok: true; status: number; json: unknown } | { ok: false; reason: ChatFailure }> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (res.status === 429) return { ok: false, reason: 'rate_limited' };
    if (res.status >= 500) return { ok: false, reason: 'unavailable' };
    if (!res.ok) return { ok: false, reason: 'failed' };
    return { ok: true, status: res.status, json: await res.json() };
  } catch (e) {
    return { ok: false, reason: (e as Error).name === 'AbortError' ? 'timeout' : 'unavailable' };
  } finally {
    clearTimeout(timer);
  }
}

export async function askMatch(req: ChatRequest, url = askUrl, timeoutMs = 25_000): Promise<AskResult> {
  if (!url) return { ok: false, reason: 'not_configured' };
  const res = await post(url, req, timeoutMs);
  if (!res.ok) return res;
  const body = res.json as ChatResponse;
  if (!body || !STATUSES.has(body.status) || !Array.isArray(body.tools)) return { ok: false, reason: 'failed' };
  if (body.status === 'error') return { ok: false, reason: body.error === 'timeout' ? 'timeout' : 'unavailable' };
  if (typeof body.answer !== 'string' || !body.answer) return { ok: false, reason: 'failed' };
  return { ok: true, response: body };
}

/** /api/chat-overlay next to /api/ask. */
export const chatOverlayUrl = (ask: string | null = askUrl) => (ask ? new URL('/api/chat-overlay', ask).toString() : null);

/**
 * Turns an answer into a chat_answer order for the stage, starting at `showAtS`.
 * The stream replays files and takes no new orders, so the UI draws this order itself.
 */
export async function chatToOverlay(
  answer: ChatResponse,
  opts: { mode: Mode; language: Language; showAtS: number },
  url = chatOverlayUrl(),
  timeoutMs = 10_000,
): Promise<OverlayResult> {
  if (!url) return { ok: false, reason: 'not_configured' };
  const res = await post(url, { answer, mode: opts.mode, language: opts.language, show_at_s: opts.showAtS, slot: 'side_panel' }, timeoutMs);
  if (!res.ok) return res;
  const order = res.json as ChatAnswerOrder;
  if (!order || order.type !== 'chat_answer' || typeof order.overlay_id !== 'string' || typeof order.show_at_s !== 'number') {
    return { ok: false, reason: 'failed' };
  }
  return { ok: true, order };
}
