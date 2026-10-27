import { useId } from 'react';
import type { ChainLink } from '../../contracts/overlay';
import { usePrefs } from '../../i18n/prefs';
import { chainActionLabel } from '../../i18n/labels';
import { asSent, surname } from '../../i18n/strings';
import { buildGoalPlay, PITCH_H, PITCH_W, playViewBox, toSvg } from '../../logic/goalPlay';

/**
 * Tactics board for a goal: the chain drawn on a 105 × 68 pitch from the engine's coordinates.
 * Only the players in the chain appear (the engine has no positions for anyone else).
 * Steps appear in t_s order, one every STEP_MS.
 */

const STEP_MS = 450;

export interface GoalPlayBoardProps {
  links: ChainLink[];
  /** Side of the scoring team, for the colour of the ball's path. */
  side: 'home' | 'away';
  /** Space the run opened, from invisible_assist.space_opened_m. */
  spaceOpened?: number | null;
}

export function GoalPlayBoard({ links, side, spaceOpened }: GoalPlayBoardProps) {
  const { lang } = usePrefs();
  const uid = useId().replace(/:/g, '');
  const play = buildGoalPlay(links);
  const order = new Map(
    [...links.map((l, i) => ({ l, i }))].sort((a, b) => a.l.t_s - b.l.t_s).map(({ i }, n) => [i, n]),
  );
  const delay = (link: number) => ({ animationDelay: `${(order.get(link) ?? 0) * STEP_MS}ms` });
  const ball = `var(--bi-team-${side})`;
  const rival = `var(--bi-team-${side === 'home' ? 'away' : 'home'})`;
  const label = links.map((l) => `${l.player}: ${chainActionLabel(l, lang)}`).join('; ');
  // Zoom in on the play; strokes, dots and text shrink with the zoom so they keep their size on screen.
  const vb = playViewBox(play);
  const k = vb[2] / PITCH_W;
  const sw = (n: number) => n * k;
  // Labels on the right half of the board are written leftwards, so they never run off its edge.
  const leftward = (x: number) => x > vb[0] + vb[2] * 0.6;

  return (
    <svg className="gp" viewBox={vb.join(' ')} role="img" aria-label={label}>
      <defs>
        {[['ball', ball], ['run', 'var(--bi-accent)'], ['rival', rival]].map(([k, c]) => (
          <marker key={k} id={`${uid}-${k}`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill={c} />
          </marker>
        ))}
      </defs>

      <g className="gp-pitch" fill="none" strokeWidth={sw(3)}>
        <rect x="0" y="0" width={PITCH_W} height={PITCH_H} />
        <line x1="525" y1="0" x2="525" y2={PITCH_H} />
        <circle cx="525" cy="340" r="91.5" />
        <rect x="0" y="138.5" width="165" height="403" />
        <rect x="885" y="138.5" width="165" height="403" />
        <rect x="0" y="248.5" width="55" height="183" />
        <rect x="995" y="248.5" width="55" height="183" />
        <rect x="-8" y="303.4" width="8" height="73.2" />
        <rect x="1050" y="303.4" width="8" height="73.2" />
      </g>

      {play.gaps.map((g, i) => {
        const [x1, y1] = toSvg(g.from);
        const [x2, y2] = toSvg(g.to);
        return (
          <line
            key={`gap-${i}`} className="gp-gap gp-fade" style={delay(g.before)} x1={x1} y1={y1} x2={x2} y2={y2}
            strokeWidth={sw(4)} strokeDasharray={`${sw(2)} ${sw(14)}`}
          />
        );
      })}

      {play.defender && (() => {
        const [x1, y1] = toSvg(play.defender.from);
        const [x2, y2] = toSvg(play.defender.to);
        return (
          <g className="gp-fade" style={delay(play.defender.link)}>
            <circle className="gp-defender-from" cx={x1} cy={y1} r={sw(14)} stroke={rival} strokeWidth={sw(4)} />
            <line
              className="gp-defender" x1={x1} y1={y1} x2={x2} y2={y2} stroke={rival} markerEnd={`url(#${uid}-rival)`}
              strokeWidth={sw(5)} strokeDasharray={`${sw(10)} ${sw(10)}`}
            />
            <text
              className="gp-label gp-label-rival" x={leftward(x1) ? x1 - sw(24) : x1 + sw(24)} y={y1 + sw(10)}
              textAnchor={leftward(x1) ? 'end' : 'start'} fontSize={sw(28)} strokeWidth={sw(8)}
            >
              {play.defender.name ? surname(play.defender.name) : ''}
              {spaceOpened != null && ` +${asSent(spaceOpened, lang)} m`}
            </text>
          </g>
        );
      })()}

      {play.steps.map((st) => {
        if (st.kind === 'dot') {
          const [cx, cy] = toSvg(st.at);
          return <circle key={st.link} className="gp-dot gp-fade" style={delay(st.link)} cx={cx} cy={cy} r={sw(14)} fill={ball} strokeWidth={sw(4)} />;
        }
        const [x1, y1] = toSvg(st.from);
        const [x2, y2] = toSvg(st.to);
        const run = st.kind === 'run';
        // A cross bends towards the middle of the pitch.
        const d = st.cross
          ? `M${x1} ${y1} Q${(x1 + x2) / 2 + (y2 - y1) * 0.25} ${(y1 + y2) / 2 + (340 - (y1 + y2) / 2) * 0.35} ${x2} ${y2}`
          : `M${x1} ${y1} L${x2} ${y2}`;
        return (
          <path
            key={st.link}
            className={`gp-step gp-${st.kind}${run ? ' gp-fade' : ''}`}
            style={delay(st.link)}
            d={d}
            pathLength={run ? undefined : 1}
            stroke={run ? 'var(--bi-accent)' : ball}
            strokeWidth={sw(7)}
            strokeDasharray={run ? `${sw(22)} ${sw(14)}` : undefined}
            markerEnd={`url(#${uid}-${run ? 'run' : 'ball'})`}
          />
        );
      })}

      {play.labels.map((l) => {
        const [x, y] = toSvg(l.at);
        return (
          <text
            key={l.link} className="gp-label gp-fade" style={delay(l.link)}
            x={leftward(x) ? x - sw(18) : x + sw(18)} y={y - sw(18)} textAnchor={leftward(x) ? 'end' : 'start'}
            fontSize={sw(34)} strokeWidth={sw(8)}
          >
            {surname(l.player)}
          </text>
        );
      })}
    </svg>
  );
}
