import * as raw from 'virtual:match-data';
import type { ChainLinkType, OverlayOrder, PitchPoint, Scoreline } from '../contracts/overlay';
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

/** An event the orders cite as evidence, with its coordinates (from events.jsonl). */
export interface PlayEvent {
  event_id: number;
  t_s: number;
  type: ChainLinkType | 'goal';
  team: string;
  player: string;
  start: PitchPoint;
  end: PitchPoint | null;
  outcome?: string | null;
  cross?: boolean;
  lines_broken?: number;
  dragged_defender?: string | null;
  dragged_defender_start?: PitchPoint | null;
  dragged_defender_end?: PitchPoint | null;
  space_opened_m?: number | null;
}

export const demoMatch = {
  matchId: raw.matchId,
  events: raw.events as StructuralEvent[],
  overlays: raw.overlays as OverlayOrder[],
  playEvents: raw.playEvents as PlayEvent[],
  teams: raw.teams as TeamsFile,
};

export const roster = buildRoster(demoMatch.teams);
