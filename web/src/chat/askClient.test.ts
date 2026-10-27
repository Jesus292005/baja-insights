import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ChatRequest, ChatResponse } from '../contracts/overlay';
import { askMatch, chatOverlayUrl, chatToOverlay } from './askClient';

const ASK = 'https://chat.example/api/ask';
const req: ChatRequest = { match_id: 'm001', question: '¿Cómo va el partido?', at: '35:00', mode: 'fan', language: 'es' };
const answer: ChatResponse = {
  match_id: 'm001', question: req.question, at_s: 2100, status: 'answered', answer: 'Van 0-1.', tools: ['get_match_state'],
};

const reply = (status: number, body: unknown) =>
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })));

afterEach(() => vi.unstubAllGlobals());

describe('askMatch', () => {
  it('returns the answer as sent', async () => {
    reply(200, answer);
    expect(await askMatch(req, ASK)).toEqual({ ok: true, response: answer });
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe(ASK);
  });

  it('keeps not_tracked answers, which are answers too', async () => {
    reply(200, { ...answer, status: 'not_tracked', answer: 'No medimos la distancia.' });
    const res = await askMatch(req, ASK);
    expect(res.ok && res.response.status).toBe('not_tracked');
  });

  it('tells a rate limit apart from a failure', async () => {
    reply(429, { error: 'rate_limited', detail: 'too many questions this minute' });
    expect(await askMatch(req, ASK)).toEqual({ ok: false, reason: 'rate_limited' });
    reply(500, {});
    expect(await askMatch(req, ASK)).toEqual({ ok: false, reason: 'unavailable' });
    reply(400, {});
    expect(await askMatch(req, ASK)).toEqual({ ok: false, reason: 'failed' });
  });

  it('turns an error response into a failure, never into an empty answer', async () => {
    reply(200, { ...answer, status: 'error', answer: null, error: 'timeout' });
    expect(await askMatch(req, ASK)).toEqual({ ok: false, reason: 'timeout' });
    reply(200, { ...answer, answer: '' });
    expect(await askMatch(req, ASK)).toEqual({ ok: false, reason: 'failed' });
  });

  it('says it is not configured without a URL', async () => {
    expect(await askMatch(req, null)).toEqual({ ok: false, reason: 'not_configured' });
  });
});

describe('chatToOverlay', () => {
  it('posts to /api/chat-overlay next to /api/ask and returns the order', async () => {
    const order = { overlay_id: 'chat-1', type: 'chat_answer', show_at_s: 2100, slot: 'side_panel' };
    reply(200, order);
    const url = chatOverlayUrl(ASK);
    expect(url).toBe('https://chat.example/api/chat-overlay');
    expect(await chatToOverlay(answer, { mode: 'fan', language: 'es', showAtS: 2100 }, url)).toEqual({ ok: true, order });
    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]!.body));
    expect(body).toEqual({ answer, mode: 'fan', language: 'es', show_at_s: 2100, slot: 'side_panel' });
  });

  it('rejects something that is not a chat_answer order', async () => {
    reply(200, { overlay_id: 'x', type: 'top3', show_at_s: 1 });
    const res = await chatToOverlay(answer, { mode: 'fan', language: 'es', showAtS: 1 }, 'https://chat.example/api/chat-overlay');
    expect(res).toEqual({ ok: false, reason: 'failed' });
  });
});
