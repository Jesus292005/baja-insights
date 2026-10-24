import { useEffect } from 'react';
import type { AppConfig } from '../app/config';
import { useMatchRuntime } from '../app/useMatchRuntime';
import { MatchBug } from '../components/shell/shell';
import { Stage } from '../components/stage/Stage';
import { PrefsProvider } from '../i18n/prefs';

/**
 * The overlay alone: 1920×1080, transparent background, no controls. Mode and language come
 * from the URL so each output (fan ES, analyst EN…) is its own browser source.
 */
export function BroadcastView({ config }: { config: AppConfig }) {
  const mode = config.mode ?? 'fan';
  const lang = config.lang ?? 'es';
  const rt = useMatchRuntime(config, mode, lang);

  useEffect(() => {
    const root = document.documentElement;
    delete root.dataset.theme;
    root.dataset.view = 'broadcast';
    root.lang = lang;
  }, [lang]);

  // Space pauses or resumes the replay, for rehearsals.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== 'Space' || !rt.replay) return;
      e.preventDefault();
      if (rt.replay.getState().playing) rt.replay.pause();
      else rt.replay.play();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [rt.replay]);

  return (
    <PrefsProvider mode={mode} lang={lang}>
      <Stage
        showing={rt.showing}
        orders={rt.orders}
        variant="broadcast"
        bug={config.bug ? <div className="slot-bug"><MatchBug state={rt.snap.state} clockUpdate={rt.snap.clock} variant="broadcast" /></div> : null}
      />
    </PrefsProvider>
  );
}
