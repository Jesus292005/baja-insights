import { useRef, useState, type FormEvent } from 'react';
import { askMatch, askUrl, chatToOverlay, type ChatFailure } from '../../chat/askClient';
import type { ChatAnswerOrder, ChatResponse, ConnectionStatus } from '../../contracts/overlay';
import { usePrefs } from '../../i18n/prefs';
import { clock, surname, t as fill } from '../../i18n/strings';

type Answer = Exclude<ChatResponse, { status: 'error' }>;

interface Message {
  id: number;
  role: 'user' | 'match';
  text: string;
  atS: number;
  /** The raw answer, kept to send it to /api/chat-overlay. */
  response?: Answer;
  screen?: 'sending' | 'shown' | 'failed';
}

export interface AskTheMatchProps {
  matchId: string;
  t: number;
  connection: ConnectionStatus;
  /** Current MVP leader from the ranking the engine sent, for the "why is X first?" suggestion. */
  leader?: string | null;
  /** Puts a chat_answer order on this browser's stage. */
  onShowOrder?: (order: ChatAnswerOrder) => void;
}

/** "Ask the match". Answers only from the agent's response; never fills a gap itself. */
export function AskTheMatch({ matchId, t, connection, leader, onShowOrder }: AskTheMatchProps) {
  const { s, lang, mode } = usePrefs();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<{ question: string; reason: ChatFailure } | null>(null);
  const nextId = useRef(1);
  const offline = connection === 'offline' || connection === 'reconnecting';
  const disabled = !askUrl || offline || busy;

  const suggestions = [
    ...(leader ? [fill(s.chat.suggestionLeader, { player: surname(leader) })] : []),
    ...s.chat.suggestions,
  ].slice(0, 3);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || disabled) return;
    const atS = Math.floor(t);
    setFailed(null);
    setBusy(true);
    setMessages((m) => [...m, { id: nextId.current++, role: 'user', text: q, atS }]);
    const history = messages.slice(-6).map((m) => ({ role: m.role, text: m.text }));
    const res = await askMatch({ match_id: matchId, question: q, at: clock(atS), mode, language: lang, favorite_team: null, history });
    setBusy(false);
    if (!res.ok) {
      setMessages((m) => m.slice(0, -1));
      setFailed({ question: q, reason: res.reason });
      setDraft(q);
      return;
    }
    setDraft('');
    setMessages((m) => [...m, { id: nextId.current++, role: 'match', text: res.response.answer, atS, response: res.response }]);
  }

  async function showOnScreen(id: number) {
    const msg = messages.find((m) => m.id === id);
    if (!msg?.response || !onShowOrder) return;
    const mark = (screen: Message['screen']) => setMessages((all) => all.map((m) => (m.id === id ? { ...m, screen } : m)));
    mark('sending');
    const res = await chatToOverlay(msg.response, { mode, language: lang, showAtS: Math.floor(t) });
    if (!res.ok) return mark('failed');
    onShowOrder(res.order);
    mark('shown');
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void ask(draft);
  };

  const statusNote = (st?: Answer['status']) =>
    st === 'not_tracked' ? s.chat.notTracked : st === 'not_found' ? s.chat.notFound : st === 'no_prediction' ? s.chat.noPrediction : null;

  const failureText = (reason: ChatFailure) =>
    reason === 'rate_limited' ? s.chat.rateLimited : reason === 'timeout' ? s.chat.timeout : s.chat.error;

  return (
    <section className="rail-panel chat" aria-labelledby="rail-chat">
      <header className="rail-head">
        <h2 id="rail-chat">{s.chat.title}</h2>
      </header>
      <p className="note">{s.chat.intro}</p>
      <ol className="chat-log" aria-live="polite">
        {messages.map((m) => {
          const st = m.response?.status;
          return (
            <li key={m.id} className={`bubble bubble-${m.role}${st && st !== 'answered' ? ' bubble-limited' : ''}`}>
              <span className="sr-only">{m.role === 'user' ? s.chat.you : s.chat.match}: </span>
              {statusNote(st) && <span className="bubble-flag">{statusNote(st)}</span>}
              {m.text}
              {m.response && (
                <span className="evidence">
                  <span className="evidence-label">{s.chat.answeredWith}</span>
                  {m.response.tools.map((x) => <code key={x} className="evidence-chip">{x}</code>)}
                  {mode === 'analyst' && <code className="evidence-chip">{clock(m.atS)}</code>}
                  {mode === 'analyst' && m.response.evidence?.map((id) => <code key={id} className="evidence-chip">#{id}</code>)}
                </span>
              )}
              {m.response && onShowOrder && (
                <button
                  type="button"
                  className="btn-link bubble-action"
                  disabled={m.screen === 'sending' || m.screen === 'shown'}
                  onClick={() => void showOnScreen(m.id)}
                >
                  {m.screen === 'sending' ? s.chat.showing : m.screen === 'shown' ? s.chat.shown : m.screen === 'failed' ? s.chat.showFailed : s.chat.showOnScreen}
                </button>
              )}
            </li>
          );
        })}
        {busy && <li className="bubble bubble-match bubble-wait">{s.chat.sending}</li>}
      </ol>
      {!askUrl ? (
        <p className="chat-state">{s.chat.unavailable}</p>
      ) : offline ? (
        <p className="chat-state">{s.chat.offline}</p>
      ) : failed ? (
        <p className={`chat-state${failed.reason === 'rate_limited' ? '' : ' chat-error'}`} role="alert">
          {failureText(failed.reason)}{' '}
          <button type="button" className="btn-link" onClick={() => void ask(failed.question)}>{s.status.retry}</button>
        </p>
      ) : null}
      <div className="chat-suggestions">
        {suggestions.map((q) => (
          <button key={q} type="button" className="chip-btn" disabled={disabled} onClick={() => void ask(q)}>
            {q}
          </button>
        ))}
      </div>
      <form className="chat-form" onSubmit={onSubmit}>
        <label htmlFor="chat-input" className="sr-only">{s.chat.label}</label>
        <input
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={s.chat.placeholder}
          maxLength={500}
          disabled={!askUrl || offline}
          autoComplete="off"
        />
        <button type="submit" className="btn-primary" disabled={disabled || !draft.trim()}>
          {s.chat.send}
        </button>
      </form>
    </section>
  );
}
