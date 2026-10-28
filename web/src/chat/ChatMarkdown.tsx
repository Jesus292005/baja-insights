import { Fragment } from 'react';
import { parseMarkdown, type Inline } from './markdown';

function Spans({ parts }: { parts: Inline[] }) {
  return (
    <>
      {parts.map((p, i) =>
        p.kind === 'text' ? <Fragment key={i}>{p.text}</Fragment>
        : p.kind === 'code' ? <code key={i}>{p.text}</code>
        : p.kind === 'strong' ? <strong key={i}><Spans parts={p.children} /></strong>
        : <em key={i}><Spans parts={p.children} /></em>,
      )}
    </>
  );
}

/** An agent answer, rendered from its Markdown. Text only: no HTML from the answer reaches the page. */
export function ChatMarkdown({ text }: { text: string }) {
  return (
    <div className="md">
      {parseMarkdown(text).map((b, i) => {
        if (b.kind === 'p') {
          return (
            <p key={i}>
              {b.lines.map((line, j) => (
                <Fragment key={j}>{j > 0 && <br />}<Spans parts={line} /></Fragment>
              ))}
            </p>
          );
        }
        const items = b.items.map((item, j) => <li key={j}><Spans parts={item} /></li>);
        return b.kind === 'ul' ? <ul key={i}>{items}</ul> : <ol key={i} start={b.start}>{items}</ol>;
      })}
    </div>
  );
}
