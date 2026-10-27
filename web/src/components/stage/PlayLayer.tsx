import { useId } from 'react';
import { usePrefs } from '../../i18n/prefs';
import { asSent, surname } from '../../i18n/strings';
import { buildPlay, toSvg, type MatchPlay, type Side } from '../../logic/play';

/**
 * The current play, drawn inside the pitch backdrop (1050 × 680 SVG units). Keyed by the order,
 * so each new play animates in, in t_s order, and then stays on the pitch.
 */

const STEP_MS = 450;
const teamColour = (side: Side) => `var(--bi-team-${side})`;

export function PlayLayer({ play }: { play: MatchPlay }) {
  const { lang } = usePrefs();
  const uid = useId().replace(/:/g, '');
  const drawn = buildPlay(play.links, play.goal);
  const order = new Map(
    play.links.map((l, i) => ({ l, i })).sort((a, b) => a.l.t_s - b.l.t_s).map(({ i }, n) => [i, n]),
  );
  const delay = (link: number) => ({ animationDelay: `${(order.get(link) ?? 0) * STEP_MS}ms` });
  const side = (link: number) => play.links[link]?.side ?? 'home';
  const rival = (link: number) => (side(link) === 'home' ? 'away' : 'home');
  // Labels on the right of the pitch are written leftwards, so they never run off it.
  const leftward = (x: number) => x > 760;

  return (
    <g className="pl">
      <defs>
        {(['home', 'away'] as const).map((s) => (
          <marker key={s} id={`${uid}-${s}`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3" markerHeight="3" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill={teamColour(s)} />
          </marker>
        ))}
        <marker id={`${uid}-run`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3" markerHeight="3" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--bi-accent)" />
        </marker>
      </defs>

      {drawn.gaps.map((g, i) => {
        const [x1, y1] = toSvg(g.from);
        const [x2, y2] = toSvg(g.to);
        return <line key={`gap-${i}`} className="pl-ball pl-fade" style={delay(g.before)} x1={x1} y1={y1} x2={x2} y2={y2} />;
      })}

      {drawn.defender && (() => {
        const [x1, y1] = toSvg(drawn.defender.from);
        const [x2, y2] = toSvg(drawn.defender.to);
        const r = rival(drawn.defender.link);
        const left = leftward(x1);
        return (
          <g className="pl-fade" style={delay(drawn.defender.link)}>
            <circle className="pl-defender-from" cx={x1} cy={y1} r="12" stroke={teamColour(r)} />
            <line className="pl-defender" x1={x1} y1={y1} x2={x2} y2={y2} stroke={teamColour(r)} markerEnd={`url(#${uid}-${r})`} />
            <text className="pl-label pl-label-rival" x={left ? x1 - 20 : x1 + 20} y={y1 + 8} textAnchor={left ? 'end' : 'start'}>
              {drawn.defender.name ? surname(drawn.defender.name) : ''}
              {play.spaceOpened != null && ` +${asSent(play.spaceOpened, lang)} m`}
            </text>
          </g>
        );
      })()}

      {drawn.steps.map((st) => {
        const colour = teamColour(side(st.link));
        if (st.kind === 'marker') {
          const [cx, cy] = toSvg(st.at);
          if (st.marker === 'duel') {
            return <rect key={st.link} className="pl-marker pl-fade" style={delay(st.link)} x={cx - 11} y={cy - 11} width="22" height="22" transform={`rotate(45 ${cx} ${cy})`} fill={colour} />;
          }
          if (st.marker === 'pressure') {
            return <circle key={st.link} className="pl-marker pl-pressure pl-fade" style={delay(st.link)} cx={cx} cy={cy} r="13" stroke={colour} />;
          }
          return <circle key={st.link} className="pl-marker pl-fade" style={delay(st.link)} cx={cx} cy={cy} r="13" fill={colour} />;
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
            className={`pl-step pl-${st.kind}${run ? ' pl-fade' : ''}`}
            style={delay(st.link)}
            d={d}
            pathLength={run ? undefined : 1}
            stroke={run ? 'var(--bi-accent)' : colour}
            markerEnd={`url(#${uid}-${run ? 'run' : side(st.link)})`}
          />
        );
      })}

      {drawn.labels.map((l) => {
        const [x, y] = toSvg(l.at);
        const left = leftward(x);
        return (
          <text key={l.link} className="pl-label pl-fade" style={delay(l.link)} x={left ? x - 16 : x + 16} y={y - 16} textAnchor={left ? 'end' : 'start'}>
            {surname(l.player)}
          </text>
        );
      })}
    </g>
  );
}
