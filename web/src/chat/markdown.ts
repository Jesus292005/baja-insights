/**
 * The small Markdown subset the Ask-the-match agent writes (agents/baja_agents/ask.py, INSTRUCTIONS):
 * paragraphs, "- " and "1. " lists, **bold**, *italics* and `code`. Anything else stays as text.
 *
 * It parses to plain data and ChatMarkdown builds React elements from it, so no HTML from the
 * answer ever reaches the page.
 */

export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'strong' | 'em'; children: Inline[] };

export type Block =
  | { kind: 'p'; lines: Inline[][] }
  | { kind: 'ul'; items: Inline[][] }
  | { kind: 'ol'; start: number; items: Inline[][] };

// **bold** or __bold__, *italics*, `code`. Underscore italics are left out: they would break names like player_a.
const INLINE = /(\*\*|__)(?=\S)(.+?)(?<=\S)\1|\*(?=[^\s*])(.+?)(?<=[^\s*])\*|`([^`]+)`/g;

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ kind: 'text', text: text.slice(last, at) });
    if (m[2] !== undefined) out.push({ kind: 'strong', children: parseInline(m[2]) });
    else if (m[3] !== undefined) out.push({ kind: 'em', children: parseInline(m[3]) });
    else out.push({ kind: 'code', text: m[4] });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ kind: 'text', text: text.slice(last) });
  return out;
}

const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  let open = null as Block | null; // the cast keeps TS from narrowing it to null: close() reassigns it
  let listText: string[] = []; // raw text of the open list's items, joined with continuation lines
  let paraLines: string[] = [];

  const close = () => {
    if (open?.kind === 'p') open.lines = paraLines.map(parseInline);
    else if (open) open.items = listText.map(parseInline);
    if (open) blocks.push(open);
    open = null;
    listText = [];
    paraLines = [];
  };

  for (const raw of source.replace(/\r\n?/g, '\n').split('\n')) {
    const line = raw.trimEnd();
    const bullet = BULLET.exec(line);
    const numbered = NUMBERED.exec(line);
    if (!line.trim()) {
      close();
    } else if (bullet || numbered) {
      const kind = bullet ? 'ul' : 'ol';
      if (open?.kind !== kind) {
        close();
        open = kind === 'ul' ? { kind, items: [] } : { kind, start: Number(numbered![1]), items: [] };
      }
      listText.push(bullet ? bullet[1] : numbered![2]);
    } else if (open && open.kind !== 'p' && /^\s/.test(raw)) {
      listText[listText.length - 1] += ` ${line.trim()}`; // an indented line continues the item
    } else {
      if (open?.kind !== 'p') {
        close();
        open = { kind: 'p', lines: [] };
      }
      const heading = HEADING.exec(line);
      paraLines.push(heading ? `**${heading[1]}**` : line.trim()); // no headings in a chat bubble: shown in bold
    }
  }
  close();
  return blocks;
}
