import { useRef, useState, type FormEvent } from 'react';
import { askMatch, askUrl } from '../../chat/askClient';
import type { ChatResponse, ConnectionStatus } from '../../contracts/overlay';
import { usePrefs } from '../../i18n/prefs';
import { clock } from '../../i18n/strings';

interface Message {
  id: number;
  role: 'user' | 'match';
  text: string;
  atS: number;
  status?: ChatResponse['status'];
  tools?: string[];
  evidence?: number[];
}

export interface AskTheMatchProps {
  matchId: string;
  t: number;
  connection: ConnectionStatus;
}

/** "Ask the match". Answers only from the agent's response; never fills a gap itself. */
export function AskTheMatch({ matchId, t, connection }: AskTheMatchProps) {
  const { s, lang, mode } = usePrefs();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const nextId = useRef(1);
  const offline = connection === 'offline' || connection === 'reconnecting';
  const disabled = !askUrl || offline || busy;

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
    if (res.status === 'error') {
      setMessages((m) => m.slice(0, -1));
      setFailed(q);
      setDraft(q);
      return;
    }
    setDraft('');
    setMessages((m) => [...m, { id: nextId.current++, role: 'match', text: res.answer, atS, status: res.status, tools: res.tools, evidence: res.evidence }]);
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void ask(draft);
  };

  const statusNote = (st?: ChatResponse['status']) =>
    st === 'not_tracked' ? s.chat.notTracked : st === 'not_found' ? s.chat.notFound : st === 'no_prediction' ? s.chat.noPrediction : null;

  return (
    <section className="rail-panel chat" aria-labelledby="rail-chat">
      <header className="rail-head">
        <h2 id="rail-chat">{s.chat.title}</h2>
      </header>
      <p className="note">{s.chat.intro}</p>
      <ol className="chat-log" aria-live="polite">
        {messages.map((m) => (
          <li key={m.id} className={`bubble bubble-${m.role}${m.status && m.status !== 'answered' ? ' bubble-limited' : ''}`}>
            <span className="sr-only">{m.role === 'user' ? s.chat.you : s.chat.match}: </span>
            {statusNote(m.status) && <span className="bubble-flag">{statusNote(m.status)}</span>}
            {m.text}
            {m.role === 'match' && (m.tools?.length || mode === 'analyst') ? (
              <span className="evidence">
                <span className="evidence-label">{s.chat.answeredWith}</span>
                {m.tools?.map((x) => <code key={x} className="evidence-chip">{x}</code>)}
                {mode === 'analyst' && <code className="evidence-chip">{clock(m.atS)}</code>}
                {mode === 'analyst' && m.evidence?.map((id) => <code key={id} className="evidence-chip">#{id}</code>)}
              </span>
            ) : null}
          </li>
        ))}
        {busy && <li className="bubble bubble-match bubble-wait">{s.chat.sending}</li>}
      </ol>
      {!askUrl ? (
        <p className="chat-state">{s.chat.unavailable}</p>
      ) : offline ? (
        <p className="chat-state">{s.chat.offline}</p>
      ) : failed ? (
        <p className="chat-state chat-error" role="alert">
          {s.chat.error}{' '}
          <button type="button" className="btn-link" onClick={() => void ask(failed)}>{s.status.retry}</button>
        </p>
      ) : null}
      <div className="chat-suggestions">
        {s.chat.suggestions.map((q) => (
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
