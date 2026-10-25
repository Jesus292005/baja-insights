import type { ChatRequest, ChatResponse } from '../contracts/overlay';

/**
 * Client for POST /api/ask (contracts/chat.schema.json). The URL comes from VITE_ASK_URL;
 * without it the chat shows that it is not connected instead of making anything up.
 */

export const askUrl: string | null = import.meta.env.VITE_ASK_URL || null;

const STATUSES = new Set(['answered', 'not_tracked', 'not_found', 'no_prediction', 'error']);

export async function askMatch(req: ChatRequest, url = askUrl, timeoutMs = 25_000): Promise<ChatResponse> {
  const fail = (error: 'timeout' | 'engine_unavailable' | 'agent_failed'): ChatResponse => ({
    match_id: req.match_id, question: req.question, at_s: typeof req.at === 'number' ? req.at : 0,
    status: 'error', answer: null, tools: [], error,
  });
  if (!url) return fail('engine_unavailable');
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal: ctrl.signal,
    });
    if (!res.ok) return fail(res.status >= 500 ? 'agent_failed' : 'engine_unavailable');
    const body = (await res.json()) as ChatResponse;
    if (!body || !STATUSES.has(body.status) || !Array.isArray(body.tools)) return fail('agent_failed');
    if (body.status !== 'error' && (typeof body.answer !== 'string' || !body.answer)) return fail('agent_failed');
    return body;
  } catch (e) {
    return fail((e as Error).name === 'AbortError' ? 'timeout' : 'engine_unavailable');
  } finally {
    clearTimeout(timer);
  }
}
