import { createContext, useContext, type ReactNode } from 'react';
import type { Language, Mode } from '../contracts/overlay';
import { strings, type Strings } from './strings';

export interface Prefs {
  mode: Mode;
  lang: Language;
  s: Strings;
}

const PrefsContext = createContext<Prefs>({ mode: 'fan', lang: 'es', s: strings.es });

export function PrefsProvider({ mode, lang, children }: { mode: Mode; lang: Language; children: ReactNode }) {
  return <PrefsContext.Provider value={{ mode, lang, s: strings[lang] }}>{children}</PrefsContext.Provider>;
}

export const usePrefs = () => useContext(PrefsContext);
