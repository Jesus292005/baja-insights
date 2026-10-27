"""Insight engine: feeds events into MatchState and runs the detectors.

Usage::

    engine = InsightEngine(Roster.load())
    for event in stream:
        for insight in engine.process(event):
            send_to_agents(insight)

Every insight follows ``contracts/insight.schema.json``. The engine never calls
an LLM, so the same events always produce the same insights.
"""

from __future__ import annotations

from ..contract import STRUCTURAL_EVENTS, distance, fmt_clock, in_opponent_half, period_of
from ..roster import Roster
from . import params as P
from .scoring import (
    chain_action_label, chain_weight, duel_bar, priority_card, priority_duel,
    priority_milestone, priority_mvp, priority_phase, split_credit,
)
from .state import MatchState, PlayerState

FLANK_MATCHUPS = {("LD", "EI"), ("LI", "ED"), ("ED", "LI"), ("EI", "LD")}
ORDINALS = {3: "tercera", 6: "sexta", 9: "novena", 12: "duodécima"}
# Fields of a card change in the insights (contract v1.1: reason_code and reason_params are optional)
CARD_CHANGE_KEYS = ("attribute", "from", "to", "delta", "reason", "reason_code", "reason_params",
                    "overall_from", "overall_to")
COUNT_WORDS = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho"}


# Pitch coordinates of the dragged defender, only on scripted off-ball runs
DEFENDER_POINT_KEYS = ("dragged_defender_start", "dragged_defender_end")


def chain_link(event: dict, credit: float) -> dict:
    """One link of a goal chain. ``action`` is the Spanish label; ``type``, ``lines_broken`` and ``cross``
    (only on crosses) come from the event, so each language can build its own label (contract v1.1).

    ``start`` and ``end`` are the event's pitch coordinates, so the interface can draw the play.
    Off-ball runs also carry the dragged defender, with his coordinates when the event has them.
    Both are optional fields added to contract v1.1."""
    link = {"event_id": event["event_id"], "player": event["player"], "action": chain_action_label(event),
            "credit": credit, "t_s": event["t_s"], "type": event["type"],
            "lines_broken": int(event.get("lines_broken") or 0),
            "start": point(event.get("start")), "end": point(event.get("end"))}
    if event.get("cross"):
        link["cross"] = True
    if event["type"] == "off_ball_run" and event.get("dragged_defender"):
        link["dragged_defender"] = event["dragged_defender"]
        for key in DEFENDER_POINT_KEYS:
            if event.get(key) is not None:
                link[key] = point(event[key])
    return link


def point(value) -> list[float] | None:
    """A copy of an ``[x, y]`` point in metres, or None."""
    return None if value is None else [value[0], value[1]]


class InsightEngine:
    def __init__(self, roster: Roster, match_id: str | None = None):
        self.roster = roster
        self.state = MatchState(roster, match_id)
        self.insights: list[dict] = []
        self._counter = 0
        self._last_mvp_t: dict[str, int] = {}
        self._last_mvp_global = -10**9
        self._milestones: set[tuple[str, int]] = set()
        self._last_milestone_t = -10**9
        self._phase_emitted: set[tuple[str, str, int]] = set()
        self._last_phase_minute = 0
        self._pending_duels: dict[tuple[str, str], dict] = {}
        self._last_duel: dict[tuple[str, str], dict] = {}
        self._pending_cards: list[dict] = []
        self._dribbles: dict[str, list[tuple[int, int]]] = {}  # player -> (t, event_id) of duels won on the ball
        self._pass_runs: dict[str, list[int]] = {}  # player -> event ids of his completed passes in a row
        self._last_win: dict[str, tuple[int, str, int]] = {}  # team -> (t, player, event_id) of its last ball won
        self._last_spell_t: dict[str, int] = {}
        self.goal_chains: dict[int, dict] = {}

    # ------------------------------------------------------------------ API
    def run(self, events) -> list[dict]:
        for event in events:
            self.process(event)
        return self.insights

    def process(self, event: dict) -> list[dict]:
        st = self.state
        out: list[dict] = []
        pid = event.get("possession_id")
        if event["type"] in STRUCTURAL_EVENTS or (pid is not None and pid != st.current_pid):
            out += self._resolve_pending()

        prev_pid = st.current_pid
        points_before = {n: ps.raw_points for n, ps in st.players.items()}
        stats_before = {n: dict(ps.stats) for n, ps in st.players.items()}
        ranking_before = st.ranking()

        effects = st.apply(event)
        ev = effects["event"]
        touched = [n for n, ps in st.players.items()
                   if ps.raw_points != points_before.get(n) or ps.stats != stats_before.get(n)]

        cards = self._card_rules(effects)
        out += self._mvp(ev, ranking_before, touched, cards)
        out += self._milestones_check(ev, touched, cards)
        for c in cards:
            if c.get("defer"):
                self._pending_cards.append(c)
            elif not c.get("used"):
                out.append(self._card_insight(c))
        if "goal" in effects:
            out.append(self._goal_chain(effects["goal"]))
        if "duel_pair" in effects:
            self._register_duel(effects["duel_pair"], ev)
        out += self._phases(ev)
        if prev_pid is not None and prev_pid != st.current_pid:
            out += self._possession_spell(prev_pid, ev)
        if ev["type"] == "half_time":
            out.append(self._match_keys())
        if ev["type"] == "match_end":
            out += self._resolve_pending()
            out.append(self._top3())
            out.append(self._summary())

        out.sort(key=lambda i: (i["t_s"], -i["priority"]))
        for ins in out:
            self._counter += 1
            ins["insight_id"] = f"i{self._counter:02d}"
        self.insights.extend(out)
        return out

    # -------------------------------------------------------------- builder
    def _make(self, kind: str, priority: float, players: list[str], team: str | None,
              facts: dict, evidence: list[int], t: int | None = None) -> dict:
        t = self.state.t if t is None else t
        return {
            "insight_id": None, "match_id": self.state.match_id, "period": period_of(t),
            "minute": t // 60, "second": t % 60, "t_s": t, "type": kind,
            "priority": round(priority, 2), "players": players, "team": team,
            "facts": facts, "evidence": sorted(set(evidence)),
        }

    # ---------------------------------------------------------------- cards
    def _card_rules(self, effects: dict) -> list[dict]:
        st = self.state
        ev = effects["event"]
        kind = ev["type"]
        found: list[dict] = []

        def add(player, attribute, delta, reason, evidence, extra=None, defer=False, code=None, params=None):
            change = st.card_change(player, attribute, delta, reason, ev["event_id"], code, params)
            if change:
                found.append({"player": player, "change": change, "evidence": evidence,
                              "extra": extra or {}, "defer": defer, "t": st.t,
                              "possession_id": ev.get("possession_id")})

        if kind == "pass" and ev.get("outcome") == "complete":
            lines = ev.get("lines_broken") or 0
            if effects.get("difficulty", 0) >= P.CARD_VISION_MIN_DIFFICULTY and lines >= P.CARD_VISION_MIN_LINES:
                reason = f"pase que rompió {lines} líneas" + (" bajo presión" if ev.get("under_pressure") else "")
                add(ev["player"], "vision", 2, reason, [ev["event_id"]],
                    {"pass_distance_m": round(distance(ev["start"], ev["end"]), 1),
                     "pass_difficulty": effects["difficulty"]}, defer=True,
                    code="line_breaking_pass", params={"lines": lines, "under_pressure": bool(ev.get("under_pressure"))})

        if kind == "recovery" and effects.get("opp_half_recovery"):
            ps = st.players[ev["player"]]
            window = [(t, e) for t, e in ps.opp_half_recovery_times if st.t - t <= P.CARD_DEFENSE_WINDOW_S]
            n = len(window)
            if n >= P.CARD_DEFENSE_RECOVERIES and n % P.CARD_DEFENSE_RECOVERIES == 0:
                word = ORDINALS.get(n, f"{n}.ª")
                add(ev["player"], "defensa", 2,
                    f"{word} recuperación en campo rival en menos de 10 minutos",
                    [e for _, e in window],
                    {"recoveries_window": f"{fmt_clock(window[0][0])}-{fmt_clock(st.t)}"},
                    code="opp_half_recoveries", params={"count": n, "window_min": P.CARD_DEFENSE_WINDOW_S // 60})

        if kind == "off_ball_run":
            speed = ev.get("speed_kmh") or 0
            if speed >= P.CARD_PACE_KMH:
                add(ev["player"], "ritmo", 1, f"desmarque a {round(speed)} km/h", [ev["event_id"]],
                    {"run_speed_kmh": speed}, code="run_speed", params={"speed_kmh": round(speed)})

        if kind == "duel" and ev.get("outcome") == "won":
            pos = st.possessions.get(ev.get("possession_id"))
            if pos is not None and pos.owner == ev.get("team"):  # won by the player on the ball: a dribble
                runs = self._dribbles.setdefault(ev["player"], [])
                runs.append((st.t, ev["event_id"]))
                window = [(t, e) for t, e in runs if st.t - t <= P.CARD_DRIBBLE_WINDOW_S]
                if len(window) >= P.CARD_DRIBBLE_COUNT and len(window) % P.CARD_DRIBBLE_COUNT == 0:
                    count = COUNT_WORDS.get(len(window), str(len(window)))  # in words: a reason carries one figure
                    add(ev["player"], "regate", 1,
                        f"{count} regates ganados en menos de {P.CARD_DRIBBLE_WINDOW_S // 60} minutos",
                        [e for _, e in window],
                        code="dribbles", params={"count": len(window), "window_min": P.CARD_DRIBBLE_WINDOW_S // 60})

        if kind == "shot" and ev.get("outcome") != "goal":  # a run that ends in a goal has its own rule
            pos = st.possessions.get(ev.get("possession_id"))
            for run in (pos.off_ball_runs if pos else []):
                space = run.get("space_opened_m") or 0
                if run.get("team") == ev.get("team") and run.get("dragged_defender") \
                        and space >= P.CARD_OFF_BALL_SHOT_MIN_SPACE_M:
                    add(run["player"], "sin_balon", 1,
                        f"arrastró a {run['dragged_defender']} y la jugada terminó en remate",
                        [run["event_id"], ev["event_id"]], {"space_opened_m": space},
                        code="run_ended_in_shot", params={"dragged_defender": run["dragged_defender"]})

        if kind == "shot":
            speed = ev.get("speed_kmh") or 0
            if speed >= P.CARD_SHOT_SPEED_KMH and ev.get("outcome") in ("goal", "saved"):
                add(ev["player"], "disparo", 1, f"remate a {round(speed)} km/h", [ev["event_id"]],
                    {"shot_speed_kmh": speed}, code="shot_speed", params={"speed_kmh": round(speed)})

        if kind == "goal":
            pos = st.possessions.get(ev.get("possession_id"))
            for run in (pos.off_ball_runs if pos else []):
                space = run.get("space_opened_m") or 0
                if run.get("team") == ev.get("team") and run.get("dragged_defender") and space >= P.CARD_OFF_BALL_MIN_SPACE_M:
                    defender = st.players.get(run["dragged_defender"])
                    who = "al central" if defender and defender.position == "DFC" else f"a {run['dragged_defender']}"
                    add(run["player"], "sin_balon", 3, f"arrastró {who} y abrió el espacio del gol",
                        [run["event_id"], ev["event_id"]], {"space_opened_m": space},
                        code="run_opened_goal", params={"dragged_defender": run["dragged_defender"],
                                                       "dragged_position": defender.position if defender else None})

        if kind == "pass":
            run = self._pass_runs.setdefault(ev["player"], [])
            if ev.get("outcome") == "complete":
                run.append(ev["event_id"])
                if len(run) % P.CARD_PASS_STREAK == 0 and ev.get("position") != "POR":
                    add(ev["player"], "vision", 1, f"{len(run)} pases completados seguidos", run[-5:],
                        code="pass_streak", params={"count": len(run)})
            else:
                run.clear()

        if kind == "recovery" or (kind in ("tackle", "duel") and ev.get("outcome") == "won"):
            # a counter-attack starts in the own half; winning it higher up has the recoveries card
            own_half = ev.get("start") is not None and not in_opponent_half(ev["start"][0], ev["team"], st.home)
            if own_half:
                self._last_win[ev["team"]] = (st.t, ev["player"], ev["event_id"])
            else:
                self._last_win.pop(ev["team"], None)
        if kind == "shot" and ev.get("team") in self._last_win:
            won_t, winner, won_id = self._last_win.pop(ev["team"])
            secs = st.t - won_t
            if P.CARD_RECOVERY_SHOT_MIN_S <= secs <= P.CARD_RECOVERY_SHOT_S:
                add(winner, "fisico", 1, f"recuperación en campo propio que terminó en remate en {secs} segundos",
                    [won_id, ev["event_id"]], code="recovery_to_shot",
                    params={"seconds": secs, "shooter": ev["player"]})

        if kind == "shot" and ev.get("outcome") == "saved" and (ev.get("xg") or 0) >= P.CARD_SAVE_MIN_XG:
            keeper = next((n for n, ps in st.players.items() if ps.position == "POR"
                           and ps.team == st.roster.opponent(ev["team"]) and ps.on_since is not None), None)
            if keeper:
                xg = round(ev["xg"], 2)
                add(keeper, "defensa", 2 if xg >= P.CARD_SAVE_BIG_XG else 1, f"atajada a un remate de xG {xg:.2f}",
                    [ev["event_id"]], code="big_save", params={"xg": xg, "shooter": ev["player"]})

        if kind in ("duel", "tackle"):
            for name in (ev.get("player"), ev.get("opponent")):
                ps = st.players.get(name)
                if ps and ps.duel_streak and ps.duel_streak % P.CARD_DUEL_STREAK == 0:
                    add(name, "fisico", 1, f"{ps.duel_streak} duelos ganados seguidos", [ev["event_id"]],
                        code="duel_streak", params={"count": ps.duel_streak})
        return found

    def _card_insight(self, c: dict) -> dict:
        ch = c["change"]
        facts = {"player": c["player"], "attribute": ch["attribute"], "from": ch["from"], "to": ch["to"],
                 "delta": ch["delta"], "reason": ch["reason"], "reason_code": ch["reason_code"],
                 "reason_params": ch["reason_params"], "overall_from": ch["overall_from"],
                 "overall_to": ch["overall_to"], **c["extra"]}
        team = self.state.players[c["player"]].team
        return self._make("card_upgrade", priority_card(ch["delta"]), [c["player"]], team,
                          facts, c["evidence"], t=c["t"])

    @staticmethod
    def _card_change_fact(c: dict) -> dict:
        ch = c["change"]
        return {k: ch[k] for k in CARD_CHANGE_KEYS}

    # ----------------------------------------------------------------- MVP
    def _mvp(self, ev: dict, before: list, touched: list[str], cards: list[dict]) -> list[dict]:
        st = self.state
        if st.t < P.MVP_MIN_T_S or st.t - self._last_mvp_global < P.MVP_GLOBAL_COOLDOWN_S:
            return []
        after = st.ranking()
        best = None
        for name in touched:
            new_rank = st.rank_of(name, after)
            old_rank = st.rank_of(name, before) or len(after) + 1
            if new_rank is None or new_rank > P.MVP_ANNOUNCE_TOP or new_rank >= old_rank:
                continue
            if new_rank != 1 and st.t - self._last_mvp_t.get(name, -10**9) < P.MVP_PLAYER_COOLDOWN_S:
                continue  # reaching first place is always news
            climb = old_rank - new_rank
            if best is None or (new_rank, -climb) < (best[1], -best[3]):
                best = (name, new_rank, old_rank, climb)
        if best is None:
            return []
        name, new_rank, old_rank, _ = best
        ps = st.players[name]
        self._last_mvp_t[name] = st.t
        self._last_mvp_global = st.t
        facts = {"player": name, "from_rank": old_rank, "to_rank": new_rank, "mvp_score": dict(after)[name],
                 "trigger_event_id": ev["event_id"]}
        if new_rank == 1:
            facts["previous_leader"] = before[0][0] if before else None
        else:
            facts["leader"] = after[0][0]
        facts["stats"] = _headline_stats(ps)
        facts["expected_for_role"] = st.expected(ps)
        facts["ranking"] = st.ranking_rows(P.MVP_RANKING_TOP, after)
        evidence = [ev["event_id"]] + _recent_top_events(st, ps, st.t, 10 * 60, 3)
        for c in cards:
            if c["player"] == name and not c.get("used") and not c.get("defer"):
                facts["card_change"] = self._card_change_fact(c)
                facts.update({k: v for k, v in c["extra"].items() if k == "recoveries_window"})
                evidence += c["evidence"]
                c["used"] = True
        return [self._make("mvp_rank_change", priority_mvp(old_rank, new_rank), [name], ps.team, facts, evidence)]

    # ----------------------------------------------------------- milestones
    def _milestones_check(self, ev: dict, touched: list[str], cards: list[dict]) -> list[dict]:
        st = self.state
        if st.t - self._last_milestone_t < P.MILESTONE_GLOBAL_GAP_S:
            return []
        for name in touched:
            ps = st.players[name]
            key = (name, st.period)
            if key in self._milestones or ps.minutes(st.t) < P.MILESTONE_MIN_MINUTES:
                continue
            role_delta = st.vs_role(ps)
            hit = [k for k, v in P.MILESTONE_THRESHOLDS.items() if ps.stats[k] >= v]
            if role_delta < P.MILESTONE_MIN_VS_ROLE or not hit:
                continue
            self._milestones.add(key)
            self._last_milestone_t = st.t
            defensive = "recoveries" in hit or "duels_won" in hit
            facts = {
                "player": name, "position": ps.position,
                "profile": "defensive" if defensive else "creative",
                "stats": {k: ps.stats[k] for k in ("recoveries", "duels_won", "duels_total",
                                                   "progressive_passes", "key_passes")},
                "expected_for_role": st.expected(ps),
                "vs_role": role_delta, "mvp_rank": st.rank_of(name),
            }
            evidence = _recent_top_events(st, ps, st.t, 45 * 60, 4) + [ev["event_id"]]
            change = st.card_change(name, "defensa" if defensive else "vision", 2 if defensive else 1,
                                    "partido defensivo por encima de lo esperado para su rol" if defensive
                                    else "partido creativo por encima de lo esperado para su rol", ev["event_id"],
                                    "standout_defensive" if defensive else "standout_creative", {})
            if change:
                facts["card_change"] = {k: change[k] for k in CARD_CHANGE_KEYS}
            for c in cards:
                if c["player"] == name and not c.get("used") and not c.get("defer"):
                    facts.setdefault("card_change", self._card_change_fact(c))
                    c["used"] = True
            return [self._make("standout_milestone", priority_milestone(role_delta), [name], ps.team,
                               facts, evidence)]
        return []

    # --------------------------------------------------------------- duels
    def _register_duel(self, pair: tuple[str, str], ev: dict) -> None:
        a, b = (self.state.players[n] for n in pair)
        if (a.position, b.position) not in FLANK_MATCHUPS:
            return
        pending = self._pending_duels.setdefault(pair, {"evidence": [], "possession_id": ev.get("possession_id")})
        pending["evidence"].append(ev["event_id"])
        pending["possession_id"] = ev.get("possession_id")

    def duel_facts(self, a: str, b: str) -> dict:
        st = self.state
        pair = st.pair_key(a, b) or (a, b)
        pa, pb = st.players[pair[0]], st.players[pair[1]]
        history = st.duel_pairs.get(pair, [])
        a_role, b_role = st.vs_role(pa), st.vs_role(pb)
        return {
            "player_a": pair[0], "player_b": pair[1], "bar": duel_bar(a_role, b_role),
            "a_vs_role": a_role, "b_vs_role": b_role,
            "duels_won_a": sum(1 for _, w, _ in history if w == pair[0]),
            "duels_won_b": sum(1 for _, w, _ in history if w == pair[1]),
            "direct_duels": len(history),
            "chances_created_a": pa.stats["key_passes"], "chances_created_b": pb.stats["key_passes"],
        }

    def _resolve_pending(self) -> list[dict]:
        st = self.state
        out = []
        for pair, pending in list(self._pending_duels.items()):
            facts = self.duel_facts(*pair)
            last = self._last_duel.get(pair)
            # a flip only counts once the bar clearly changed side, not when it wobbles around 0
            flipped = bool(last and last["bar"] * facts["bar"] < 0 and abs(facts["bar"]) >= P.DUEL_FLIP_MIN_BAR)
            if last and not flipped and st.t - last["t"] < P.DUEL_PAIR_COOLDOWN_S:
                del self._pending_duels[pair]
                continue
            facts["flipped"] = flipped
            pos = st.possessions.get(pending["possession_id"])
            evidence = list(pending["evidence"])
            if pos:
                evidence += [e for e in pos.events if st.by_id[e]["type"] in ("pass", "shot")
                             and e > pending["evidence"][0]]
            self._last_duel[pair] = {"bar": facts["bar"], "t": st.t}
            out.append(self._make("duel_state", priority_duel(facts["bar"], flipped), list(pair), None,
                                  facts, evidence))
            del self._pending_duels[pair]
        for c in self._pending_cards:
            pos = st.possessions.get(c["possession_id"])
            if pos:
                after = [st.by_id[e] for e in pos.events if e > c["change"]["event_id"]]
                shot = next((e for e in after if e["type"] == "shot"), None)
                if shot:
                    c["extra"]["led_to"] = f"remate de {shot['player']}, xG {shot.get('xg', 0):.2f}"
                    c["extra"]["led_to_event_id"] = shot["event_id"]
                    c["evidence"].append(shot["event_id"])
            out.append(self._card_insight(c))
        self._pending_cards = []
        return out

    # ------------------------------------------------------------ goal chain
    def _goal_chain(self, goal: dict) -> dict:
        st = self.state
        pos = st.possessions.get(goal.get("possession_id"))
        team = goal["team"]
        events = [st.by_id[e] for e in (pos.events if pos else []) if st.by_id[e].get("team") == team]
        shot = next((e for e in reversed(events) if e["type"] == "shot"), None)
        scorer = goal.get("player")
        assist_id = None
        for e in events:
            if e["type"] == "pass" and e.get("outcome") == "complete" and e.get("receiver") == scorer \
                    and (shot is None or e["t_s"] <= shot["t_s"]):
                assist_id = e["event_id"]
        candidates = []
        for e in events:
            if e["type"] == "goal":
                continue
            weight = chain_weight(e, e["event_id"] == assist_id)
            if weight >= P.CHAIN_MIN_WEIGHT or e is shot:
                candidates.append((e, weight))
        candidates.sort(key=lambda item: (item[0]["t_s"], item[0]["event_id"]))
        credits = split_credit([w for _, w in candidates])
        chain = [chain_link(e, c) for (e, _), c in zip(candidates, credits)]
        invisible = None
        for e, _ in candidates:
            if e["type"] == "off_ball_run":
                touched = any(x["player"] == e["player"] and x["type"] in ("pass", "shot", "recovery", "duel", "tackle")
                              for x in events)
                invisible = {"player": e["player"], "dragged_defender": e.get("dragged_defender"),
                             "space_opened_m": e.get("space_opened_m"), "touched_ball": touched}
                break
        start_t = pos.start_t if pos else goal["t_s"]
        facts = {"scoreline": dict(st.scoreline), "scorer": scorer, "assist": goal.get("assist"),
                 "xg": shot.get("xg") if shot else None, "duration_s": goal["t_s"] - start_t,
                 "chain": chain, "invisible_assist": invisible}
        self.goal_chains[goal["event_id"]] = facts
        players = [scorer] + [c["player"] for c in sorted(chain, key=lambda c: -c["credit"]) if c["player"] != scorer]
        players = list(dict.fromkeys(players))
        return self._make("goal_chain", P.PRIORITY_FIXED["goal_chain"], players, team, facts,
                          [e["event_id"] for e in events] + [goal["event_id"]])

    # --------------------------------------------------------------- phases
    def _phases(self, ev: dict) -> list[dict]:
        st = self.state
        minute = st.t // 60
        if minute <= self._last_phase_minute:
            return []
        self._last_phase_minute = minute
        end = minute * 60
        period_start = 0 if st.period == 1 else 45 * 60
        start = end - P.PHASE_WINDOW_S
        if start < period_start:
            return []
        out = []
        window = f"{fmt_clock(start)}-{fmt_clock(end)}"
        stats = {team: st.window_stats(team, start, end) for team in (st.home, st.away)}
        for team in (st.home, st.away):
            other = st.roster.opponent(team)
            s = stats[team]
            key = (team, "control", st.period)
            if key not in self._phase_emitted and s["possession_pct"] is not None \
                    and s["possession_pct"] >= P.PHASE_CONTROL_POSSESSION \
                    and (s["pass_accuracy_pct"] or 0) >= P.PHASE_CONTROL_PASS_ACCURACY \
                    and s["passes"] >= P.PHASE_CONTROL_MIN_PASSES:
                self._phase_emitted.add(key)
                facts = {"label": "control", "window": window, "possession_pct": s["possession_pct"],
                         "pass_accuracy_pct": {st.side(team): s["pass_accuracy_pct"],
                                               st.side(other): stats[other]["pass_accuracy_pct"]},
                         "passes_per_min": {st.side(team): s["passes_per_min"],
                                            st.side(other): stats[other]["passes_per_min"]}}
                out.append(self._make("team_phase", priority_phase("control"), [], team, facts, [], t=end))
            key = (team, "pressure_shift", st.period)
            if st.period == 2 and key not in self._phase_emitted:
                first = st.window_stats(team, 0, 45 * 60)
                avg = round(first["recoveries_opp_half"] / 4.5, 1)
                threshold = max(P.PHASE_PRESSURE_MIN_RECOVERIES, P.PHASE_PRESSURE_RATIO * avg)
                if s["recoveries_opp_half"] >= threshold:
                    self._phase_emitted.add(key)
                    rec_ids = [e for t, opp, e in st.team_recoveries[team] if opp and start <= t < end]
                    facts = {"label": "pressure_shift", "window": window,
                             "recoveries_opp_half": s["recoveries_opp_half"],
                             "recoveries_opp_half_first_half_avg_10min": avg,
                             "def_action_height_m": s["def_action_height_m"],
                             "def_action_height_first_half_m": first["def_action_height_m"]}
                    out.append(self._make("team_phase", priority_phase("pressure_shift"), [], team, facts,
                                          rec_ids[-5:], t=end))
        return out

    def _possession_spell(self, pid: int, ev: dict) -> list[dict]:
        """A long possession that just ended: how many passes, how long, how many players, how it ended."""
        st = self.state
        pos = st.possessions.get(pid)
        if pos is None or pos.owner is None:
            return []
        events = [st.by_id[e] for e in pos.events]
        passes = [e for e in events if e["type"] == "pass" and e.get("outcome") == "complete" and e["team"] == pos.owner]
        if len(passes) < P.PHASE_SPELL_MIN_PASSES:
            return []
        if st.t - self._last_spell_t.get(pos.owner, -10**9) < P.PHASE_SPELL_COOLDOWN_S:
            return []
        self._last_spell_t[pos.owner] = st.t
        last = [e for e in events if e["team"] == pos.owner][-1]
        if last["type"] == "shot":
            ended = "goal" if last.get("outcome") == "goal" else "shot"
        elif last.get("out_of_play"):
            ended = "out"
        elif ev["type"] == "foul" or (ev.get("set_piece") == "free_kick" and ev.get("team") == pos.owner):
            ended = "foul"
        else:
            ended = "lost"
        end = max(e["t_s"] for e in events)
        touches = {}
        for e in passes:
            touches[e["player"]] = touches.get(e["player"], 0) + 1
        players = [n for n, _ in sorted(touches.items(), key=lambda kv: -kv[1])]
        facts = {"label": "possession_spell", "window": f"{fmt_clock(pos.start_t)}-{fmt_clock(end)}",
                 "passes": len(passes), "duration_s": end - pos.start_t, "players_involved": len(players),
                 "ended_in": ended}
        return [self._make("team_phase", priority_phase("possession_spell"), players[:3], pos.owner, facts,
                           [e["event_id"] for e in passes])]

    # ------------------------------------------------------------ half time
    def _match_keys(self) -> dict:
        st = self.state
        end = st.t
        stats = {team: st.window_stats(team, 0, end) for team in (st.home, st.away)}
        keys = {}
        evidence = list(st.goals)
        for team in (st.home, st.away):
            s = stats[team]
            other = st.roster.opponent(team)
            candidates = []
            possession = s["possession_pct"] or 50
            if s["recoveries_opp_half"] >= 4 and possession < 50:
                top = _top_player(st, team, "recoveries_opp_half")
                extra = f", {top[1]} de {top[0]}" if top and top[1] >= 2 else ""
                candidates.append((3, {"code": "win_ball_high", "key": "recuperar en campo rival",
                                       "evidence": f"{s['recoveries_opp_half']} recuperaciones en mitad rival{extra}"}))
            if s["shots_on_target"] <= 1:
                candidates.append((2, {"code": "more_bodies_in_box", "key": "llegar con más gente al área",
                                       "evidence": f"{s['shots_on_target']} tiro a puerta en el primer tiempo"
                                       if s["shots_on_target"] == 1 else
                                       f"{s['shots_on_target']} tiros a puerta en el primer tiempo"}))
            if possession >= 55:
                candidates.append((3, {"code": "keep_possession", "key": "mantener la posesión",
                                       "evidence": f"{possession}% de posesión y {s['pass_accuracy_pct']}% de pases completados"}))
            for pair, history in st.duel_pairs.items():
                a, b = pair
                mine = a if st.players[a].team == team else b
                theirs = b if mine == a else a
                if (st.players[a].position, st.players[b].position) not in FLANK_MATCHUPS or len(history) < 3:
                    continue
                last3 = history[-3:]
                lost = sum(1 for _, w, _ in last3 if w != mine)
                if lost >= 2:
                    candidates.append((2, {"code": "win_flank", "key": f"recuperar la banda de {mine}",
                                           "evidence": f"{theirs} ganó {lost} de los últimos 3 duelos"}))
                    evidence += [e for _, _, e in last3]
            if not candidates:
                candidates.append((1, {"code": "create_danger", "key": "generar más peligro",
                                       "evidence": f"xG {s['xg']:.2f} en el primer tiempo"}))
            candidates.sort(key=lambda c: -c[0])
            keys[team] = [c for _, c in candidates[:2]]
        facts = {"scoreline": dict(st.scoreline),
                 "xg": {st.side(t): stats[t]["xg"] for t in stats},
                 "possession_pct": {st.side(t): stats[t]["possession_pct"] for t in stats},
                 "keys": keys, "no_prediction": True}
        return self._make("match_keys", P.PRIORITY_FIXED["match_keys"], [], None, facts, evidence)

    # ------------------------------------------------------------- full time
    def _top3(self) -> dict:
        st = self.state
        ranking = st.ranking()[:3]
        top = []
        evidence = []
        for rank, (name, score) in enumerate(ranking, start=1):
            ps = st.players[name]
            key_events = [e for _, e in sorted(ps.point_events, key=lambda pe: -pe[0])[:3]]
            evidence += key_events
            top.append({"rank": rank, "player": name, "team": ps.team, "position": ps.position,
                        "mvp_score": score, "why": self._why(ps)[:3], "key_events": key_events})
        facts = {"final_scoreline": dict(st.scoreline), "top3": top}
        return self._make("top3", P.PRIORITY_FIXED["top3"], [n for n, _ in ranking], None, facts, evidence)

    def _why(self, ps: PlayerState) -> list[str]:
        st = self.state
        s = ps.stats
        exp = st.expected(ps)
        reasons: list[tuple[float, str]] = []
        for facts in self.goal_chains.values():
            inv = facts.get("invisible_assist")
            if inv and inv["player"] == ps.name:
                reasons.append((5, "desmarque que abrió un gol sin tocar el balón"))
            chain = facts["chain"]
            if chain and chain[0]["player"] == ps.name and chain[0]["action"] in ("recuperación", "entrada ganada"):
                reasons.append((4, "inició la jugada de un gol"))
            for link in chain:
                if link["player"] == ps.name and link["action"].startswith("pase que rompió"):
                    reasons.append((4, f"{link['action']} en un gol de su equipo"))
        if s["goals"]:
            reasons.append((6, f"{s['goals']} gol" + ("es" if s["goals"] > 1 else "")))
        if s["assists"]:
            reasons.append((5, f"{s['assists']} asistencia" + ("s" if s["assists"] > 1 else "")))
        if s["recoveries_opp_half"] >= 3:
            reasons.append((3.5, f"{s['recoveries_opp_half']} recuperaciones en campo rival"))
        expected = exp["recoveries"]
        if s["recoveries"] >= expected + 2:
            if expected > 0 and s["recoveries"] >= 2 * expected:
                text = f"{s['recoveries']} recuperaciones, el doble o más de lo esperado para su rol"
            else:
                text = f"{s['recoveries']} recuperaciones, {round(s['recoveries'] - expected)} más de lo esperado para su rol"
            reasons.append((3, text))
        if s["duels_total"] >= 4 and s["duels_won"] / s["duels_total"] >= 0.7:
            reasons.append((2.5, f"{s['duels_won']} de {s['duels_total']} duelos ganados"))
        if s["line_breaking_passes"] >= 3:
            reasons.append((2.5, f"{s['line_breaking_passes']} pases que rompieron líneas"))
        if s["key_passes"] >= 2:
            reasons.append((2, f"{s['key_passes']} pases clave"))
        fastest = max((e.get("speed_kmh") or 0 for e in st.events
                       if e["type"] == "shot" and e.get("player") == ps.name), default=0)
        if fastest >= 105:
            reasons.append((1.5, f"remate a {round(fastest)} km/h"))
        seen, ordered = set(), []
        for _, text in sorted(reasons, key=lambda r: -r[0]):
            if text not in seen:
                seen.add(text)
                ordered.append(text)
        return ordered or ["partido regular por encima de lo esperado para su rol"]

    def _summary(self) -> dict:
        st = self.state
        stats = {team: st.window_stats(team, 0, st.t + 1) for team in (st.home, st.away)}
        xg = {st.side(t): stats[t]["xg"] for t in stats}
        possession = {st.side(t): stats[t]["possession_pct"] for t in stats}
        goals = []
        for gid in st.goals:
            g = st.by_id[gid]
            goals.append({"event_id": gid, "t_s": g["t_s"], "team": g["team"], "scorer": g["player"],
                          "assist": g.get("assist")})
        phases = [{"team": i["team"], "label": i["facts"]["label"], "window": i["facts"]["window"]}
                  for i in self.insights if i["type"] == "team_phase"]
        story = []
        for ph in phases:
            start_min = int(ph["window"].split("-")[0].split(":")[0])
            if ph["label"] == "control":
                story.append(f"{ph['team']} controló el juego con la pelota entre el {ph['window'].replace('-', ' y el ')}")
            elif ph["label"] == "pressure_shift":
                story.append(f"{ph['team']} cambió el partido con presión alta desde el {start_min}")
        for g in goals:
            chain = self.goal_chains.get(g["event_id"], {})
            inv = chain.get("invisible_assist")
            first = chain.get("chain", [{}])[0].get("player") if chain.get("chain") else None
            line = f"{g['team']} anotó en el {g['t_s'] // 60} con gol de {g['scorer']}"
            if inv and not inv.get("touched_ball"):
                line += f", en una jugada que nació de {first} y un desmarque de {inv['player']} sin tocar el balón"
            story.append(line)
        story.sort(key=lambda s: _first_number(s))
        xg_leader = max(stats, key=lambda t: stats[t]["xg"])
        pos_leader = max(stats, key=lambda t: stats[t]["possession_pct"] or 0)
        mvp_name = st.ranking()[0][0]
        mvp_team = st.players[mvp_name].team
        if xg_leader != pos_leader:
            verdict = f"{xg_leader} generó más peligro aunque tuvo menos la pelota"
        else:
            verdict = f"{xg_leader} dominó la pelota y también generó más peligro"
        facts = {"final_scoreline": dict(st.scoreline), "xg": xg, "possession_pct": possession,
                 "goals": goals, "phases": phases, "story": story, "who_really_won": verdict,
                 "who_really_won_basis": {"xg_leader": xg_leader, "possession_leader": pos_leader,
                                          "mvp": mvp_name, "mvp_team": mvp_team}}
        return self._make("match_summary", P.PRIORITY_FIXED["match_summary"], [], None, facts,
                          list(st.goals))


# ---------------------------------------------------------------- helpers

def _headline_stats(ps: PlayerState) -> dict:
    keys = ("recoveries", "recoveries_opp_half", "duels_won", "key_passes", "progressive_passes",
            "line_breaking_passes", "shots", "goals", "assists")
    return {k: ps.stats[k] for k in keys if ps.stats[k]}


def _recent_top_events(st: MatchState, ps: PlayerState, now: int, window: int, n: int) -> list[int]:
    """The player's n highest-scoring positive actions within the last ``window`` seconds."""
    rows = [(pts, e) for pts, e in ps.point_events
            if pts > 0 and e in st.by_id and st.by_id[e]["t_s"] >= now - window]
    rows.sort(key=lambda pe: (-pe[0], pe[1]))
    return [e for _, e in rows[:n]]


def _top_player(st: MatchState, team: str, stat: str) -> tuple[str, int] | None:
    rows = [(n, ps.stats[stat]) for n, ps in st.players.items() if ps.team == team]
    rows.sort(key=lambda r: -r[1])
    return rows[0] if rows and rows[0][1] else None


def _first_number(text: str) -> int:
    import re
    m = re.search(r"\b(\d{1,3})\b", text)
    return int(m.group(1)) if m else 0
