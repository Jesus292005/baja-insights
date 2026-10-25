import * as raw from 'virtual:match-data';
import type { OverlayOrder, Scoreline } from '../contracts/overlay';
import { buildRoster, type TeamsFile } from './roster';

/** Events the replay uses to play the stream service's part: scoreline and phases. */
export interface StructuralEvent {
  type: 'match_start' | 'goal' | 'half_time' | 'second_half_start' | 'match_end';
  t_s: number;
  period: 1 | 2;
  scoreline?: Scoreline;
  home?: string;
  away?: string;
}

export const demoMatch = {
  matchId: raw.matchId,
  events: raw.events as StructuralEvent[],
  overlays: raw.overlays as OverlayOrder[],
  teams: raw.teams as TeamsFile,
};

export const roster = buildRoster(demoMatch.teams);
