"""tp_core — shared foundation for the AI Travel Planner.

Provides the three things every other package needs: typed fail-fast
configuration, structured JSON logging, and a small exception hierarchy.
"""

from tp_core.exceptions import ConfigError, TravelPlannerError
from tp_core.logging import configure_logging, get_logger
from tp_core.settings import Settings, get_settings

__all__ = [
    "ConfigError",
    "Settings",
    "TravelPlannerError",
    "configure_logging",
    "get_logger",
    "get_settings",
]
