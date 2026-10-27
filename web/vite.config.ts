import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

const REPO = resolve(__dirname, '..');

/** Events the replay needs to act as the stream service: scoreline and match phases. */
const STRUCTURAL = new Set(['match_start', 'goal', 'half_time', 'second_half_start', 'match_end']);

/**
 * `virtual:match-data` bundles the demo match from the repo so the UI can replay it without a server.
 * BAJA_MATCH picks the folder in data/ (default m001). BAJA_OVERLAYS=mocks uses mocks/overlays_sample.json.
 * Only the structural events and the events the orders cite as evidence are bundled, not the whole events.jsonl.
 */
/** Where the page fetches the illustrative positions (3 MB): a file of its own, not part of the bundle. */
const POSITIONS_URL = '/match-data/positions.json';
const positionsPath = () => resolve(REPO, 'data', process.env.BAJA_MATCH ?? 'm001', 'positions.json');

function matchData(): Plugin {
  const publicId = 'virtual:match-data';
  const internalId = '\0' + publicId;
  return {
    name: 'baja-match-data',
    resolveId: (id) => (id === publicId ? internalId : undefined),
    // The positions file is served in dev and copied next to the build, loaded only when drawn.
    configureServer(server) {
      server.middlewares.use(POSITIONS_URL, (_req, res) => {
        if (!existsSync(positionsPath())) {
          res.statusCode = 404;
          res.end();
          return;
        }
        res.setHeader('Content-Type', 'application/json');
        res.end(readFileSync(positionsPath()));
      });
    },
    generateBundle() {
      if (existsSync(positionsPath())) {
        this.emitFile({ type: 'asset', fileName: POSITIONS_URL.slice(1), source: readFileSync(positionsPath()) });
      }
    },
    load(id) {
      if (id !== internalId) return undefined;
      const match = process.env.BAJA_MATCH ?? 'm001';
      const eventsPath = resolve(REPO, 'data', match, 'events.jsonl');
      const overlaysPath = process.env.BAJA_OVERLAYS === 'mocks'
        ? resolve(REPO, 'mocks', 'overlays_sample.json')
        : resolve(REPO, 'data', match, 'overlays.json');
      const teamsPath = resolve(REPO, 'mocks', 'teams.json');
      [eventsPath, overlaysPath, teamsPath].forEach((p) => this.addWatchFile(p));

      const allEvents = readFileSync(eventsPath, 'utf8')
        .split(/\r?\n/)
        .filter((line) => line.trim())
        .map((line) => JSON.parse(line));
      const events = allEvents
        .filter((e) => STRUCTURAL.has(e.type))
        .map(({ type, t_s, period, scoreline, home, away }) => ({ type, t_s, period, scoreline, home, away }));
      const overlays = JSON.parse(readFileSync(overlaysPath, 'utf8'));
      // The plays behind each graphic: only the events the orders cite as evidence, with their coordinates.
      const cited = new Set<number>(overlays.flatMap((o: { evidence?: number[] }) => o.evidence ?? []));
      const keep = ['event_id', 't_s', 'type', 'team', 'player', 'possession_id', 'start', 'end', 'outcome', 'cross', 'lines_broken',
        'dragged_defender', 'dragged_defender_start', 'dragged_defender_end', 'space_opened_m'];
      const playEvents = allEvents
        .filter((e) => cited.has(e.event_id) && Array.isArray(e.start))
        .map((e) => Object.fromEntries(keep.filter((k) => e[k] !== undefined).map((k) => [k, e[k]])));
      const teams = JSON.parse(readFileSync(teamsPath, 'utf8'));

      return [
        `export const matchId = ${JSON.stringify(match)};`,
        `export const events = ${JSON.stringify(events)};`,
        `export const overlays = ${JSON.stringify(overlays)};`,
        `export const playEvents = ${JSON.stringify(playEvents)};`,
        `export const teams = ${JSON.stringify(teams)};`,
        `export const positionsUrl = ${JSON.stringify(existsSync(positionsPath()) ? POSITIONS_URL : null)};`,
      ].join('\n');
    },
  };
}

export default defineConfig({
  plugins: [react(), matchData()],
  server: { port: 5173, fs: { allow: [REPO] } },
  build: { outDir: 'dist', sourcemap: true },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
} as Parameters<typeof defineConfig>[0]);
