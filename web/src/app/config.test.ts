import { describe, expect, it } from 'vitest';
import { hrefWithSource, readConfig, replayQuery } from './config';

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

  it('reads the cinema view at /cine and /cinema', () => {
    expect(readConfig(loc('?mode=fan', '/cine')).view).toBe('cinema');
    expect(readConfig(loc('', '/cinema/')).view).toBe('cinema');
  });
});

describe('hrefWithSource', () => {
  it('keeps the query and drops the replay start time when going live', () => {
    expect(hrefWithSource('live', loc('?mode=fan&t=10:00'))).toBe('/?mode=fan&source=live');
    expect(hrefWithSource('replay', loc('?source=live&lang=en'))).toBe('/?source=replay&lang=en');
  });
});

describe('replayQuery', () => {
  it('keeps the replay playing in the view it opens, at the same speed', () => {
    const q = replayQuery(3795.6, { playing: true, speed: 60, skip: true });
    expect(q).toBe('&t=3795&speed=60&skip=1');
    const c = readConfig({ pathname: '/cine', search: `?mode=fan${q}` });
    expect(c.autoplay).toBe(true);
    expect(c.speed).toBe(60);
    expect(c.startAt).toBe(3795);
  });

  it('opens paused only when the replay was paused', () => {
    const q = replayQuery(100, { playing: false, speed: 1, skip: false });
    expect(readConfig({ pathname: '/cine', search: `?${q.slice(1)}` }).autoplay).toBe(false);
  });
});
