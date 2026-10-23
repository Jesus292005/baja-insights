"""Template texts used when an agent fails, times out, the budget runs out or a check fails.

They only use values from the insight, so they always pass ``checks.check_variant``.
"""

from __future__ import annotations

from .models import VARIANT_KEYS

ATTRIBUTES = {
    "ritmo": ("Ritmo", "Pace"), "disparo": ("Disparo", "Shooting"), "vision": ("Visión", "Vision"),
    "regate": ("Regate", "Dribbling"), "defensa": ("Defensa", "Defending"), "fisico": ("Físico", "Physical"),
    "sin_balon": ("Sin balón", "Off-ball"),
}
STATS = {  # (plural es, plural en, singular es, singular en)
    "goals": ("goles", "goals", "gol", "goal"),
    "assists": ("asistencias", "assists", "asistencia", "assist"),
    "recoveries_opp_half": ("recuperaciones en campo rival", "recoveries in the opposition half",
                            "recuperación en campo rival", "recovery in the opposition half"),
    "recoveries": ("recuperaciones", "recoveries", "recuperación", "recovery"),
    "duels_won": ("duelos ganados", "duels won", "duelo ganado", "duel won"),
    "key_passes": ("pases clave", "key passes", "pase clave", "key pass"),
    "line_breaking_passes": ("pases que rompen líneas", "line-breaking passes", "pase que rompe líneas", "line-breaking pass"),
    "progressive_passes": ("pases progresivos", "progressive passes", "pase progresivo", "progressive pass"),
}
KEYS_EN = {
    "win_ball_high": "win the ball high", "more_bodies_in_box": "get more players into the box",
    "keep_possession": "keep the ball", "create_danger": "create more danger",
}


def surname(name: str) -> str:
    return name.split(". ", 1)[-1]


def stat_phrase(stats: dict, key: str, lang: int) -> str:
    return f"{stats[key]} {STATS[key][lang + 2 if stats[key] == 1 else lang]}"


def stat_list(stats: dict, lang: int, top: int = 3) -> str:
    return ", ".join([stat_phrase(stats, k, lang) for k in STATS if stats.get(k)][:top])


def readable_stats(stats: dict) -> dict[str, list[str]]:
    """Every stat already worded, zeros included, so the model copies labels instead of guessing them."""
    out = {"es": [], "en": []}
    for key in STATS:
        if key in stats:
            out["es"].append(stat_phrase(stats, key, 0))
            out["en"].append(stat_phrase(stats, key, 1))
    if "duels_total" in stats and "duels_won" in stats:
        out["es"].append(f"{stats['duels_won']} de {stats['duels_total']} duelos ganados")
        out["en"].append(f"{stats['duels_won']} of {stats['duels_total']} duels won")
    return out


def _mvp(f: dict) -> dict:
    p, r, s = surname(f["player"]), f["to_rank"], f["mvp_score"]
    prev = f.get("previous_leader")
    return {
        "fan_es": (f"{p}, número {r}" if r == 1 else f"{p} sube al {r}.º",
                   f"{p} sube al puesto {r} de la carrera por el MVP." + (f" Deja atrás a {surname(prev)}." if prev else "")),
        "analyst_es": (f"{p}: del {f['from_rank']}.º al {r}.º",
                       f"Puntaje MVP {s}. {stat_list(f['stats'], 0)}."),
        "fan_en": (f"{p} is number {r}" if r == 1 else f"{p} climbs to {r}",
                   f"{p} moves up to {r} in the MVP race." + (f" {surname(prev)} drops behind." if prev else "")),
        "analyst_en": (f"{p}: {f['from_rank']} to {r}",
                       f"MVP score {s}. {stat_list(f['stats'], 1)}."),
    }


def _duel(f: dict) -> dict:
    a, b, bar = surname(f["player_a"]), surname(f["player_b"]), f["bar"]
    leader = a if bar > 0 else b if bar < 0 else None
    if leader and f["flipped"]:
        fan_es, fan_en = f"{leader} le da la vuelta al duelo.", f"{leader} turns the duel around."
    elif leader:
        fan_es, fan_en = f"{leader} va ganando el duelo.", f"{leader} is winning the duel."
    else:
        fan_es, fan_en = "Duelo parejo por ahora.", "Even duel so far."
    won = f"{f['duels_won_a']}-{f['duels_won_b']}"
    return {
        "fan_es": (f"{a} vs {b}", fan_es),
        "analyst_es": ("Duelo directo", f"{a} {f['a_vs_role']:+.2f} sobre su rol, {b} {f['b_vs_role']:+.2f}. "
                                        f"Duelos ganados {won} en {f['direct_duels']} directos."),
        "fan_en": (f"{a} vs {b}", fan_en),
        "analyst_en": ("Head-to-head", f"{a} {f['a_vs_role']:+.2f} vs role, {b} {f['b_vs_role']:+.2f}. "
                                       f"Duels won {won} in {f['direct_duels']} direct duels."),
    }


def _standout(f: dict) -> dict:
    p, st = surname(f["player"]), f["stats"]
    if f["profile"] == "defensive":
        titles = ("El que no se ve", "The unseen one")
        fan_es = f"{p} está en todas: {st.get('recoveries', 0)} recuperaciones."
        fan_en = f"{p} is everywhere: {st.get('recoveries', 0)} recoveries."
    else:
        titles = ("Fábrica de juego", "Chance factory")
        fan_es = f"{p} pone a jugar a su equipo: {st.get('key_passes', 0)} pases clave."
        fan_en = f"{p} gets the team playing: {st.get('key_passes', 0)} key passes."
    return {
        "fan_es": (titles[0], fan_es),
        "analyst_es": (f"{p} por encima de su rol", f"{f['vs_role']:+.2f} sobre lo esperado para un {f['position']}. {stat_list(st, 0)}."),
        "fan_en": (titles[1], fan_en),
        "analyst_en": (f"{p} above the role",f"{f['vs_role']:+.2f} above the {f['position']} baseline. {stat_list(st, 1)}."),
    }


def _card(f: dict) -> dict:
    p, d = surname(f["player"]), f["delta"]
    es, en = ATTRIBUTES[f["attribute"]]
    return {
        "fan_es": (f"+{d} {es}", f"{p}: {f['reason']}."),
        "analyst_es": (f"+{d} {es}", f"{es} de {f['from']} a {f['to']}: {f['reason']}. Media {f['overall_from']} a {f['overall_to']}."),
        "fan_en": (f"+{d} {en}", f"{p} earns +{d} {en}."),
        "analyst_en": (f"+{d} {en}", f"{en} from {f['from']} to {f['to']}. Overall {f['overall_from']} to {f['overall_to']}."),
    }


def _goal(f: dict) -> dict:
    scorer, first = surname(f["scorer"]), surname(f["chain"][0]["player"])
    score = f"{f['scoreline']['home']}-{f['scoreline']['away']}"
    chain = ", ".join(surname(link["player"]) for link in f["chain"])
    inv = f.get("invisible_assist")
    extra_es = f" {surname(inv['player'])} abrió el espacio sin tocar el balón." if inv else ""
    extra_en = f" {surname(inv['player'])} opened the space without touching the ball." if inv else ""
    return {
        "fan_es": (f"Gol de {scorer}", f"La jugada nace en {first} y la termina {scorer}. {score}.{extra_es}"),
        "analyst_es": (f"Cadena del gol {score}", f"{chain}. xG {f['xg']} en {f['duration_s']} s."),
        "fan_en": (f"{scorer} scores", f"It starts with {first} and {scorer} finishes it. {score}.{extra_en}"),
        "analyst_en": (f"Goal chain {score}", f"{chain}. xG {f['xg']} in {f['duration_s']} s."),
    }


def _phase(f: dict, team: str, side: str) -> dict:
    if f["label"] == "control":
        acc = (f.get("pass_accuracy_pct") or {}).get(side)
        acc_es = f", {acc}% de pases completados" if acc is not None else ""
        acc_en = f", {acc}% pass accuracy" if acc is not None else ""
        return {
            "fan_es": (f"{team} manda", f"{team} tiene la pelota y no la suelta."),
            "analyst_es": ("Control de la pelota", f"{team}: {f['possession_pct']}% de posesión entre {f['window']}{acc_es}."),
            "fan_en": (f"{team} in control", f"{team} has the ball and won't give it back."),
            "analyst_en": ("Ball control", f"{team}: {f['possession_pct']}% possession between {f['window']}{acc_en}."),
        }
    return {
        "fan_es": (f"{team} aprieta arriba", f"{team} adelanta la presión y roba más cerca del área rival."),
        "analyst_es": ("Cambio de presión", f"{f['recoveries_opp_half']} recuperaciones en campo rival entre {f['window']}. "
                                            f"Altura defensiva {f['def_action_height_m']} m."),
        "fan_en": (f"{team} presses high", f"{team} pushes the press up and wins the ball closer to goal."),
        "analyst_en": ("Pressing shift", f"{f['recoveries_opp_half']} recoveries in the opposition half between {f['window']}. "
                                         f"Defensive height {f['def_action_height_m']} m."),
    }


def _keys(f: dict, t_s: int) -> dict:
    teams = list(f["keys"])
    def first_key(team, lang):
        key = f["keys"][team][0]
        if lang == 0:
            return key["key"]
        if key["code"] == "win_flank":
            return f"win back the flank of {key['key'].rsplit(' de ', 1)[-1]}"
        return KEYS_EN.get(key["code"], key["code"].replace("_", " "))
    xg = f"xG {f['xg']['home']}-{f['xg']['away']}"
    pos = f"{f['possession_pct']['home']}%-{f['possession_pct']['away']}%"
    title_es = "Claves para el segundo tiempo" if t_s >= 2700 else "Claves del partido"
    title_en = "Keys for the second half" if t_s >= 2700 else "Match keys"
    fan_es = " ".join(f"{t} necesita {first_key(t, 0)}." for t in teams)
    fan_en = " ".join(f"{t} needs to {first_key(t, 1)}." for t in teams)
    return {
        "fan_es": (title_es, fan_es),
        "analyst_es": (title_es, f"{xg}, posesión {pos}. {fan_es}"),
        "fan_en": (title_en, fan_en),
        "analyst_en": (title_en, f"{xg}, possession {pos}. {fan_en}"),
    }


def _top3(f: dict) -> dict:
    p = [surname(c["player"]) for c in f["top3"]]
    score = f"{f['final_scoreline']['home']}-{f['final_scoreline']['away']}"
    ranking = ". ".join(f"{c['rank']}. {surname(c['player'])} {c['mvp_score']}" for c in f["top3"])
    rest_es = f", seguido de {' y '.join(p[1:])}" if len(p) > 1 else ""
    rest_en = f", ahead of {' and '.join(p[1:])}" if len(p) > 1 else ""
    return {
        "fan_es": ("¿Quién ganó realmente el partido?", f"Quedó {score}, pero {p[0]} fue el mejor del partido{rest_es}."),
        "analyst_es": ("Top 3 del partido", f"{ranking}. {f['top3'][0]['why'][0].capitalize()}."),
        "fan_en": ("Who really won the match?", f"It ended {score}, but {p[0]} was the best player on the pitch{rest_en}."),
        "analyst_en": ("Match top 3", f"{ranking}."),
    }


def variants(insight: dict, home: str = "") -> dict[str, dict]:
    """Template title and text for the four versions, as {'fan_es': {'title', 'text'}, ...}."""
    f, kind = insight["facts"], insight["type"]
    if kind == "mvp_rank_change":
        out = _mvp(f)
    elif kind == "duel_state":
        out = _duel(f)
    elif kind == "standout_milestone":
        out = _standout(f)
    elif kind == "card_upgrade":
        out = _card(f)
    elif kind == "goal_chain":
        out = _goal(f)
    elif kind == "team_phase":
        team = insight["team"] or ""
        out = _phase(f, team, "home" if team == home else "away")
    elif kind == "match_keys":
        out = _keys(f, insight["t_s"])
    elif kind == "top3":
        out = _top3(f)
    else:
        raise ValueError(f"no overlay for insight type {kind}")
    return {k: {"title": out[k][0], "text": out[k][1]} for k in VARIANT_KEYS}
