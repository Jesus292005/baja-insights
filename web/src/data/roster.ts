import type { CardAttribute, Position } from '../contracts/overlay';

/** Shape of mocks/teams.json (only what the UI reads). */
export interface TeamsFile {
  match: { match_id: string; home: string; away: string; venue: string; competition: string };
  teams: {
    name: string;
    short: string;
    colors: [string, string];
    players: { number: number; name: string; position: Position; starter: boolean; card: Record<CardAttribute | 'overall', number> }[];
  }[];
}

export interface TeamRef {
  name: string;
  short: string;
  colors: [string, string];
  side: 'home' | 'away';
}

export interface PlayerRef {
  name: string;
  team: TeamRef;
  position: Position;
  number: number;
  starter: boolean;
  /** Starting card from teams.json. */
  card: Record<CardAttribute, number>;
  overall: number;
}

export interface Roster {
  home: TeamRef;
  away: TeamRef;
  players: PlayerRef[];
  team(name: string | null | undefined): TeamRef | undefined;
  player(name: string | null | undefined): PlayerRef | undefined;
}

export const CARD_ATTRIBUTES: CardAttribute[] = ['ritmo', 'disparo', 'vision', 'regate', 'defensa', 'fisico', 'sin_balon'];

export function buildRoster(file: TeamsFile): Roster {
  const refs = file.teams.map<TeamRef>((t) => ({
    name: t.name,
    short: t.short,
    colors: t.colors,
    side: t.name === file.match.home ? 'home' : 'away',
  }));
  const home = refs.find((t) => t.side === 'home') ?? refs[0];
  const away = refs.find((t) => t.side === 'away') ?? refs[1];
  const players: PlayerRef[] = file.teams.flatMap((t, i) =>
    t.players.map((p) => {
      const { overall, ...card } = p.card;
      return { name: p.name, team: refs[i], position: p.position, number: p.number, starter: p.starter, card, overall };
    }),
  );
  const byName = new Map(players.map((p) => [p.name, p]));
  const bySurname = new Map(players.map((p) => [p.name.replace(/^\S+\s+/, '').toLowerCase(), p]));
  return {
    home,
    away,
    players,
    team: (name) => refs.find((t) => t.name === name),
    player: (name) => (name ? byName.get(name) ?? bySurname.get(name.toLowerCase()) : undefined),
  };
}
