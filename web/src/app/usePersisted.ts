import { useEffect, useState } from 'react';

/**
 * Per-viewer preference in localStorage. Works without storage (private windows, blocked cookies).
 * `fromUrl` (a ?mode= or ?lang= parameter) wins over what was stored, so shared links open as sent.
 */
export function usePersisted<T extends string>(key: string, initial: T, allowed: readonly T[], fromUrl?: T | null): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    if (fromUrl) return fromUrl;
    try {
      const stored = window.localStorage.getItem(key) as T | null;
      return stored && allowed.includes(stored) ? stored : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      /* storage unavailable */
    }
  }, [key, value]);
  return [value, setValue];
}
