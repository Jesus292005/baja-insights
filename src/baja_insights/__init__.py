"""Baja-Insights: synthetic football match generator and deterministic insight engine.

The package is split in two layers that never call an LLM:

* ``baja_insights.generator`` produces a stream of match events (contract v1).
* ``baja_insights.engine`` turns that stream into insights (contract v1) and
  exposes the query functions used by the "Ask the match" agent.
"""

CONTRACT_VERSION = "1.1"
__version__ = "0.1.0"
