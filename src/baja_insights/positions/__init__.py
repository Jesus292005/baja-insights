"""Illustrative positions of the 22 players and the ball, built from the events.

See ``model.py``. The positions are only for drawing the pitch: the engine, the insights,
the agents and the chat never read them, because the events only track the player on the ball.
"""

from .model import HZ, build_positions

__all__ = ["HZ", "build_positions"]
