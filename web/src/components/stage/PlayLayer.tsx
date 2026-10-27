import { useId } from 'react';
import { usePrefs } from '../../i18n/prefs';
import { asSent, clock, surname } from '../../i18n/strings';
import { placeLabels } from '../../logic/labels';
import { buildPlay, crossControl, toSvg, type MatchPlay, type Side } from '../../logic/play';

/**
 * The current play, drawn inside the pitch backdrop (1050 × 680 SVG units). Keyed by the order,
 * so each new play animates in, in t_s order, and then stays on the pitch.
 */

const STEP_MS = 450;
/** The shot line takes this long to draw (pl-draw in stage.css); the ball lands after it. */
const DRAW_MS = 420;
const teamColour = (side: Side) => `var(--bi-team-${side})`;

/** A football: the end of a shot, so it never reads as a pass. Drawn in pitch SVG units. */
export function Ball({ cx, cy, r = 20, className, style }: { cx: number; cy: number; r?: number; className?: string; style?: React.CSSProperties }) {
  const pent = Array.from({ length: 5 }, (_, k) => {
    const a = ((-90 + 72 * k) * Math.PI) / 180;
    return [cx + Math.cos(a) * r * 0.42, cy + Math.sin(a) * r * 0.42, cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  });
  return (
    <g className={`pl-ball-end ${className ?? ''}`} style={style}>
      <circle cx={cx} cy={cy} r={r} className="pl-ball-body" />
      {pent.map(([x1, y1, x2, y2], k) => <line key={k} x1={x1} y1={y1} x2={x2} y2={y2} className="pl-ball-seam" />)}
      <polygon points={pent.map(([x, y]) => `${x},${y}`).join(' ')} className="pl-ball-patch" />
    </g>
  );
}

export function PlayLayer({ play }: { play: MatchPlay }) {
  const { lang } = usePrefs();
  const uid = useId().replace(/:/g, '');
  // The ball joins the actions of one possession; separate possessions stay apart (see buildPlay).
  const drawn = buildPlay(play.links, true);
  const order = new Map(
    play.links.map((l, i) => ({ l, i })).sort((a, b) => a.l.t_s - b.l.t_s).map(({ i }, n) => [i, n]),
  );
  const delay = (link: number) => ({ animationDelay: `${(order.get(link) ?? 0) * STEP_MS}ms` });
  const side = (link: number) => play.links[link]?.side ?? 'home';
  const rival = (link: number) => (side(link) === 'home' ? 'away' : 'home');
  const defenderText = drawn.defender
    ? `${drawn.defender.name ? surname(drawn.defender.name) : ''}${play.spaceOpened != null ? ` +${asSent(play.spaceOpened, lang)} m` : ''}`.trim()
    : null;
  // Each name takes the spot around its player that touches no other name, dot or line.
  const tagTexts = drawn.tags.map((g) => clock(g.t_s));
  const spots = placeLabels(drawn, drawn.labels.map((l) => surname(l.player)), defenderText, tagTexts);

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
        const at = spots.defender;
        return (
          <g className="pl-fade" style={delay(drawn.defender.link)}>
            <circle className="pl-defender-from" cx={x1} cy={y1} r="12" stroke={teamColour(r)} />
            <line className="pl-defender" x1={x1} y1={y1} x2={x2} y2={y2} stroke={teamColour(r)} markerEnd={`url(#${uid}-${r})`} />
            {at && defenderText && (
              <text className="pl-label pl-label-rival" x={at.x} y={at.y} textAnchor={at.anchor}>{defenderText}</text>
            )}
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
        const shot = st.kind === 'shot';
        // A cross bends towards the middle of the pitch.
        const [qx, qy] = crossControl([x1, y1], [x2, y2]);
        const d = st.cross ? `M${x1} ${y1} Q${qx} ${qy} ${x2} ${y2}` : `M${x1} ${y1} L${x2} ${y2}`;
        const path = (
          <path
            key={st.link}
            className={`pl-step pl-${st.kind}${run ? ' pl-fade' : ''}`}
            style={delay(st.link)}
            d={d}
            pathLength={run ? undefined : 1}
            stroke={run ? 'var(--bi-accent)' : colour}
            markerEnd={shot ? undefined : `url(#${uid}-${run ? 'run' : side(st.link)})`}
          />
        );
        if (!shot) return path;
        // A shot ends in the ball instead of an arrowhead.
        const ms = (order.get(st.link) ?? 0) * STEP_MS + DRAW_MS;
        return (
          <g key={st.link}>
            {path}
            <Ball cx={x2} cy={y2} className="pl-fade" style={{ animationDelay: `${ms}ms` }} />
          </g>
        );
      })}

      {drawn.labels.map((l) => {
        const at = spots.players.get(l.link);
        if (!at) return null;
        return (
          <text key={l.link} className="pl-label pl-fade" style={delay(l.link)} x={at.x} y={at.y} textAnchor={at.anchor}>
            {surname(l.player)}
          </text>
        );
      })}

      {drawn.tags.map((g, i) => {
        const at = spots.tags.get(g.link);
        if (!at) return null;
        return (
          <text key={`tag-${g.link}`} className="pl-label pl-tag pl-fade" style={delay(g.link)} x={at.x} y={at.y} textAnchor={at.anchor}>
            {tagTexts[i]}
          </text>
        );
      })}
    </g>
  );
}
