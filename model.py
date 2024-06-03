from dataclasses import dataclass


@dataclass
class Match:
    home_team: str
    guest_team: str
    odds_home: float = None
    odds_draw: float = None
    odds_guest: float = None
    tip_home: int = None
    tip_guest: int = None
