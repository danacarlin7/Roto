"""
Store classes with settings for specified daily fantasy sports site and kind of sport.
"""
from abc import ABCMeta, abstractmethod
from collections import namedtuple

LineupPosition = namedtuple('LineupPosition', ['name', 'positions'])

class BaseSettings(object):
    __metaclass__ = ABCMeta
    budget = 0
    positions = []
    max_from_one_team = None

    @classmethod
    def get_total_players(cls):
        return len(cls.positions)
# FanDuel
class FanDuelSettings(BaseSettings):
    max_from_one_team = 4

class FanDuelFootballSettings(FanDuelSettings):
    budget = 60000
    positions = [
        LineupPosition('QB', ('QB', )),
        LineupPosition('RB', ('RB', )),
        LineupPosition('RB', ('RB', )),
        LineupPosition('WR', ('WR', )),
        LineupPosition('WR', ('WR', )),
        LineupPosition('WR', ('WR', )),
        LineupPosition('TE', ('TE', )),
        LineupPosition('D', ('D', )),
        LineupPosition('K', ('K', )),
    ]

class FanDuelBaseballSettings(FanDuelSettings):
    budget = 35000
    positions = [
        LineupPosition('P', ('P',)),
        LineupPosition('C', ('C',)),
        LineupPosition('1B', ('1B',)),
        LineupPosition('2B', ('2B',)),
        LineupPosition('3B', ('3B',)),
        LineupPosition('SS', ('SS',)),
        LineupPosition('OF', ('OF',)),
        LineupPosition('OF', ('OF',)),
        LineupPosition('OF', ('OF',)),
    ]

class FanDuelBasketballSettings(FanDuelSettings):
    budget = 60000
    positions = [
        LineupPosition('PG', ('PG', )),
        LineupPosition('PG', ('PG', )),
        LineupPosition('SG', ('SG', )),
        LineupPosition('SG', ('SG', )),
        LineupPosition('SF', ('SF', )),
        LineupPosition('SF', ('SF', )),
        LineupPosition('PF', ('PF', )),
        LineupPosition('PF', ('PF', )),
        LineupPosition('C', ('C', )),
    ]

# DraftKings
class DraftKingsSettings(BaseSettings):  # pragma: no cover
    budget = 50000

class DraftKingsFootballSettings(DraftKingsSettings):
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('WR1', ('WR',)),
        LineupPosition('WR2', ('WR',)),
        LineupPosition('WR3', ('WR',)),
        LineupPosition('RB1', ('RB',)),
        LineupPosition('RB2', ('RB',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('WR', 'RB', 'TE')),
        LineupPosition('DST', ('DST',))
    ]
    max_from_one_team = 8

class DraftKingsBaseballSettings(DraftKingsSettings):
    positions = [
        LineupPosition('P', ('P', )),
        LineupPosition('P', ('P', )),
        LineupPosition('C', ('C', )),
        LineupPosition('1B', ('1B', )),
        LineupPosition('2B', ('2B', )),
        LineupPosition('3B', ('3B', )),
        LineupPosition('SS', ('SS', )),
        LineupPosition('OF', ('OF', )),
        LineupPosition('OF', ('OF', )),
        LineupPosition('OF', ('OF', )),
    ]
    max_from_one_team = 5

class DraftKingsBasketballSettings(DraftKingsSettings):
    budget = 50000
    total_players = 8
    no_position_players = 1
    positions = [
        LineupPosition('PG', ('PG', )),
        LineupPosition('SG', ('SG', )),
        LineupPosition('SF', ('SF', )),
        LineupPosition('PF', ('PF', )),
        LineupPosition('C', ('C', )),
        LineupPosition('G', ('PG', 'SG')),
        LineupPosition('F', ('SF', 'PF')),
        LineupPosition('UTIL', ('PG', 'SG', 'PF', 'SF', 'C'))
    ]