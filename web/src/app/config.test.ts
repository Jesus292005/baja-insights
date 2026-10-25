import { describe, expect, it } from 'vitest';
import { hrefWithSource, readConfig } from './config';

const loc = (search: string, pathname = '/') => ({ pathname, search });

describe('readConfig', () => {
  it('defaults to the replay even when a stream URL is configured', () => {
    expect(readConfig(loc('?ws=wss://x/ws')).source).toBe('replay');
  });

  it('goes live only when asked and a stream URL exists', () => {
    expect(readConfig(loc('?source=live&ws=wss://x/ws'))).toMatchObject({ source: 'live', streamUrl: 'wss://x/ws' });
    expect(readConfig(loc('?source=ws&ws=wss://x/ws')).source).toBe('live');
  });

  it('reads the broadcast view, mode, language and start time', () => {
    expect(readConfig(loc('?mode=analyst&lang=en&t=63:09&bug=1', '/broadcast'))).toMatchObject({
      view: 'broadcast', mode: 'analyst', lang: 'en', startAt: 3789, bug: true,
    });
    expect(readConfig(loc('?mode=x&lang=fr'))).toMatchObject({ view: 'web', mode: null, lang: null });
  });
});

describe('hrefWithSource', () => {
  it('keeps the query and drops the replay start time when going live', () => {
    expect(hrefWithSource('live', loc('?mode=fan&t=10:00'))).toBe('/?mode=fan&source=live');
    expect(hrefWithSource('replay', loc('?source=live&lang=en'))).toBe('/?source=replay&lang=en');
  });
});
