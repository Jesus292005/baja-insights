import { describe, expect, it } from 'vitest';
import { parseInline, parseMarkdown } from './markdown';

const text = (t: string) => ({ kind: 'text', text: t });

describe('parseInline', () => {
  it('reads bold, italics and code, nested too', () => {
    expect(parseInline('**Torres** va *primero* con `get_duel`')).toEqual([
      { kind: 'strong', children: [text('Torres')] }, text(' va '),
      { kind: 'em', children: [text('primero')] }, text(' con '), { kind: 'code', text: 'get_duel' },
    ]);
    expect(parseInline('**Real *Cardón* FC**')).toEqual([
      { kind: 'strong', children: [text('Real '), { kind: 'em', children: [text('Cardón')] }, text(' FC')] },
    ]);
  });

  it('leaves stray markers and snake_case alone', () => {
    expect(parseInline('3 * 2 y player_a_b')).toEqual([text('3 * 2 y player_a_b')]);
  });
});

describe('parseMarkdown', () => {
  it('splits paragraphs and lists', () => {
    const md = 'Van **0-1**.\nSigue Cardón.\n\n- Cota recupera\n- Torres\n  arrastra a su marca\n\n2. Salgado\n3. Ramírez';
    const blocks = parseMarkdown(md);
    expect(blocks.map((b) => b.kind)).toEqual(['p', 'ul', 'ol']);
    expect(blocks[0]).toMatchObject({ lines: [[text('Van '), { kind: 'strong' }, text('.')], [text('Sigue Cardón.')]] });
    expect(blocks[1]).toMatchObject({ items: [[text('Cota recupera')], [text('Torres arrastra a su marca')]] });
    expect(blocks[2]).toMatchObject({ start: 2, items: [[text('Salgado')], [text('Ramírez')]] });
  });

  it('keeps HTML as text and shows headings in bold', () => {
    expect(parseMarkdown('<img src=x onerror=alert(1)>')).toEqual([{ kind: 'p', lines: [[text('<img src=x onerror=alert(1)>')]] }]);
    expect(parseMarkdown('## Clave')).toEqual([{ kind: 'p', lines: [[{ kind: 'strong', children: [text('Clave')] }]] }]);
  });
});
