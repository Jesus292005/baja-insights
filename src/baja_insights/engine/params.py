"""Every tunable number of the engine lives here, so calibration is one file.

``docs/formulas.md`` explains each value. Change both together.
"""

# --- Pass difficulty (0..1) -------------------------------------------------
PASS_DIFFICULTY_WEIGHTS = {
    "distance": 0.30,   # min(distance / 40 m, 1)
    "pressure": 0.25,   # under_pressure
    "lines": 0.25,      # min(lines_broken / 2, 1)
    "progress": 0.20,   # clip(forward progress / 30 m, 0, 1)
}
PASS_DISTANCE_REF_M = 40.0
PASS_PROGRESS_REF_M = 30.0
PROGRESSIVE_PASS_MIN_M = 10.0

# --- Points per action (raw, before role adjustment) ------------------------
POINTS = {
    "pass_complete_base": 0.02,
    "pass_complete_difficulty": 0.25,      # * difficulty
    "pass_incomplete": -0.08,              # * (1 - difficulty)
    "key_pass": 0.20,                      # pass followed by a teammate shot in the same possession
    "assist": 0.50,                        # pass to the scorer
    "shot_base": 0.05,
    "shot_xg": 0.60,                       # * xg
    "shot_on_target": 0.05,
    "goal": 1.00,
    "recovery": 0.20,
    "recovery_opp_half": 0.15,
    "tackle_won": 0.20,
    "tackle_lost": -0.05,
    "duel_won": 0.12,
    "duel_lost": -0.06,
    "pressure": 0.02,
    "counterpress": 0.10,                  # own team recovers within COUNTERPRESS_WINDOW_S
    "foul_committed": -0.10,
    "foul_received": 0.03,
    "off_ball_run": 0.05,
    "off_ball_run_space": 0.02,            # * space_opened_m when a defender was dragged
    "off_ball_run_shot": 0.10,             # possession ends in a shot
    "off_ball_run_goal": 0.50,             # * min(space_opened_m / 10, 1) when it ends in a goal
}
COUNTERPRESS_WINDOW_S = 5

# --- Role comparison and MVP score -------------------------------------------
ROLE_STATS = ("duels_won", "recoveries", "progressive_passes", "key_passes")
ROLE_TERM_CLIP = (-1.0, 2.0)               # each stat term before averaging
ROLE_EXPECTED_FLOOR = 1.0                  # denominator floor, avoids blowups early in the match
MVP_ROLE_WEIGHT = 5.0                      # vs_role * minutes/90 * weight is added to raw points
MVP_SCALE = 7.0                            # mvp = 10 * (1 - exp(-adj / scale))

# --- Detectors ---------------------------------------------------------------
MVP_MIN_T_S = 10 * 60                      # no ranking overlays in the first 10 minutes
MVP_ANNOUNCE_TOP = 3                       # only climbs into the top 3 are announced
MVP_RANKING_TOP = 5                        # rows of facts.ranking in mvp_rank_change (contract v1.1)
MVP_PLAYER_COOLDOWN_S = 600
MVP_GLOBAL_COOLDOWN_S = 180

DUEL_PAIR_COOLDOWN_S = 300                 # unless the bar flips sign
DUEL_FLIP_MIN_BAR = 0.10                   # a flip counts only when the new bar is at least this far from 0

MILESTONE_MIN_MINUTES = 20
MILESTONE_MIN_VS_ROLE = 0.5
MILESTONE_THRESHOLDS = {"recoveries": 5, "duels_won": 5, "key_passes": 3}
MILESTONE_GLOBAL_GAP_S = 5 * 60

CARD_VISION_MIN_DIFFICULTY = 0.80
CARD_VISION_MIN_LINES = 2
CARD_DEFENSE_RECOVERIES = 3                # recoveries in the opponent half ...
CARD_DEFENSE_WINDOW_S = 10 * 60            # ... within this window
CARD_SHOT_SPEED_KMH = 105
CARD_DUEL_STREAK = 4
CARD_OFF_BALL_MIN_SPACE_M = 8.0
CARD_OFF_BALL_SHOT_MIN_SPACE_M = 5.0      # run that dragged a defender, possession ends in a shot: Sin balón +1
CARD_PACE_KMH = 30.0                       # off-ball run at this speed or more: Ritmo +1
CARD_DRIBBLE_COUNT = 2                     # duels won on the ball ...
CARD_DRIBBLE_WINDOW_S = 10 * 60            # ... within this window: Regate +1
CARD_PASS_STREAK = 20                      # completed passes in a row by an outfield player, every 20: Visión +1
CARD_RECOVERY_SHOT_MIN_S = 3               # ball won in the own half and the team shoots between 3 ...
CARD_RECOVERY_SHOT_S = 20                  # ... and 20 s later: Físico +1 (Defensa is for the recoveries card)
CARD_SAVE_MIN_XG = 0.15                    # a keeper saves a shot worth at least this: Defensa +1 (+2 from 0.30)
CARD_SAVE_BIG_XG = 0.30
CARD_ATTRIBUTE_COOLDOWN_S = 10 * 60
CARD_MAX_GAIN_PER_ATTRIBUTE = 6
CARD_MAX_VALUE = 99

PHASE_WINDOW_S = 10 * 60
LIVE_GAP_CAP_S = 8                         # longer gaps between events are dead ball
PHASE_CONTROL_POSSESSION = 62.0
PHASE_CONTROL_PASS_ACCURACY = 85.0
PHASE_CONTROL_MIN_PASSES = 30
PHASE_PRESSURE_MIN_RECOVERIES = 4
PHASE_PRESSURE_RATIO = 2.5                 # vs first-half average per 10 minutes
PHASE_SPELL_MIN_PASSES = 12                # a single possession with this many completed passes ...
PHASE_SPELL_COOLDOWN_S = 6 * 60            # ... at most one per team in this time

# --- Goal chain credit -------------------------------------------------------
CHAIN_WEIGHTS = {
    "recovery": 2.0,
    "tackle": 2.0,
    "pass_base": 0.5,
    "pass_per_line": 1.0,
    "pass_pressure": 0.5,
    "assist": 1.0,
    "off_ball_run_per_m": 0.3,
    "off_ball_run_cap": 3.5,
    "shot": 2.5,
}
CHAIN_MIN_WEIGHT = 2.0

# --- Priority (0..1) ---------------------------------------------------------
PRIORITY_FIXED = {"goal_chain": 1.0, "top3": 1.0, "match_summary": 0.9, "match_keys": 0.9}
