"""
Data structures for the schedule generation module.

A DailySchedule is a sequence of Trips for one agent on a representative weekday.
The schedule is the bridge between the profile layer (behavioral preferences) and
the simulation layer (spatiotemporal movement on the H3 grid).
"""

from __future__ import annotations
from dataclasses import dataclass, field


ACTIVITY_TYPES = (
    "work", "grocery", "shopping", "education",
    "leisure_indoor", "leisure_outdoor", "healthcare", "civic",
    "home",
)
MODES = ("car", "bus", "walk", "taxi")


@dataclass
class Trip:
    agent_id:       str
    activity_type:  str    # one of ACTIVITY_TYPES (destination activity, not travel itself)
    origin_h3:      str    # H3 cell index (resolution 10)
    dest_h3:        str
    mode:           str    # one of MODES
    departure_min:  float  # minutes from midnight (e.g. 480.0 = 08:00)
    duration_min:   float  # estimated travel time in minutes
    poi_name:       str   = ""    # OSM facility name (empty for return-home trips)
    poi_lat:        float | None = None
    poi_lon:        float | None = None


@dataclass
class DailySchedule:
    agent_id:   str
    home_h3:    str
    trips:      list[Trip] = field(default_factory=list)

    def activity_sequence(self) -> list[str]:
        """Ordered list of activity types for the day, starting from home."""
        return ["home"] + [t.activity_type for t in self.trips]
