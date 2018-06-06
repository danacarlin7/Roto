from __future__ import division
from collections import Counter, OrderedDict, defaultdict
from itertools import chain, combinations
from copy import deepcopy
from random import getrandbits, uniform
from pulp import LpProblem, LpMaximize, LpVariable, LpInteger, lpSum, LpSolverDefault, pulp
from .exceptions import LineupOptimizerException, LineupOptimizerInvalidNumberOfPlayersInPineup, LineupOptimizerIncorrectPositionName
from .settings import BaseSettings
from .player import Player
from .lineup import Lineup
from .utils import ratio, list_intersection
from collections import defaultdict
from .constants import *
import time
#from line_profiler import LineProfiler

class PositionPlaces:
    def __init__(self, min, optional):
        self.min = min
        self._init_optional = optional
        self.optional = optional

    @property
    def max(self):
        return self.min + self.optional

    def add(self):
        if self.min:
            self.min -= 1
        else:
            self.optional -= 1 if self.optional else 0

    def remove(self):
        if self.optional < self._init_optional:
            self.optional += 1
        else:
            self.min += 1


class LineupOptimizer(object):
    def __init__(self, settings):
        """
        LineupOptimizer select the best lineup for daily fantasy sports.
        :type settings: BaseSettings
        """
        self._players = []
        self._lineup = []
        self._available_positions = []
        self._available_teams = []
        self._positions = {}
        self._not_linked_positions = {}
        self._max_from_one_team = None
        self._settings = settings
        self._set_settings()
        self._removed_players = []
        self._search_threshold = 0.8
        self._min_deviation = 0.06
        self._max_deviation = 0.12
        self._site = Site.FANDUEL
        self._sport = Sport.BASEBALL

        self._num_of_lineups = 1
        self._teamConstraints = None
        self._positionConstraints = None
        self._max_exposure = None
        self._randomness = None
        self._include_injured = False
        self._min_salary = None
        self._max_salary = None

        # MLB settings
        self._no_batters_vs_opp_pitchers = False

        # NFL settings
        self._qb_wr_stack = False
        self._qb_wr_te_stack = False
        self._qb_te_stack = False
        self._rb_d_stack = False

        self._no_qb_rb_k_same_team = False
        self._no_rb_wr_te_k_same_team = False
        self._no_def_vs_opp_players = False

        self._number_of_unique_players = None


        # optimizers
        self._solver = "GLPK"
        self._message = 0
        self._threads = None
    @property
    def lineup(self):
        """
        :rtype: list[Player]
        """
        return self._lineup

    @property
    def budget(self):
        """
        :rtype: int
        """
        return self._budget

    @property
    def players(self):
        """
        :rtype: list[Player]
        """
        return [player for player in self._players
                if player not in self._removed_players]# and player not in self._lineup]

    @property
    def removed_players(self):
        """
        :rtype: list[Player]
        """
        return self._removed_players

    def _set_settings(self):
        """
        Set settings with daily fantasy sport site and kind of sport to optimizer.
        """
        self._budget = self._settings.budget
        self._total_players = self._settings.get_total_players()
        self._max_from_one_team = self._settings.max_from_one_team
        self._get_positions_for_optimizer(self._settings.positions)
        self._available_positions = self._positions.keys()

    def _get_positions_for_optimizer(self, positions_list):
        """
        Convert positions list into dict for using in optimizer.
        :type positions_list: List[LineupPosition]
        """
        positions = {}
        not_linked_positions = {}
        positions_counter = Counter([tuple(sorted(p.positions)) for p in positions_list])
        for key in positions_counter.keys():
            additional_pos = len(list(filter(
                lambda p: len(p.positions) > len(key) and list_intersection(key, p.positions), positions_list
            )))
            min_value = positions_counter[key] + len(list(filter(
                lambda p: len(p.positions) < len(key) and list_intersection(key, p.positions), positions_list
            )))
            positions[key] = PositionPlaces(min_value, additional_pos)
        for first_position, second_position in combinations(positions.items(), 2):
            if list_intersection(first_position[0], second_position[0]):
                continue
            new_key = tuple(sorted(chain(first_position[0], second_position[0])))
            if new_key in positions:
                continue
            not_linked_positions[new_key] = PositionPlaces(
                first_position[1].min + second_position[1].min,
                first_position[1].optional + second_position[1].optional
            )

        for first_position, second_position, third_position in combinations(positions.items(), 3):
            if list_intersection(first_position[0], second_position[0]):
                continue
            if list_intersection(first_position[0], third_position[0]):
                continue

            new_key = tuple(sorted(chain(first_position[0], second_position[0], third_position[0])))
            if new_key in positions:
                continue
            not_linked_positions[new_key] = PositionPlaces(
                first_position[1].min + second_position[1].min + third_position[1].min,
                first_position[1].optional + second_position[1].optional + third_position[1].optional
            )
        positions = OrderedDict(sorted(positions.items(), key=lambda item: len(item[0])))
        self._not_linked_positions = not_linked_positions
        self._positions = positions
        self._init_positions = positions

    def set_deviation(self, min_deviation, max_deviation):
        """
        Set deviation ranges for randomness mode
        :type min_deviation: float
        :type max_deviation: float
        """
        self._min_deviation = min_deviation
        self._max_deviation = max_deviation

    def reset_lineup(self):
        """
        Reset current lineup.
        """
        self._set_settings()
        self._lineup = []

    def load_players_from_CSV(self, filename):
        """
        Load player list from CSV file with passed filename.
        Calls load_players_from_CSV method from _settings object.
        :type filename: str
        """
        self._players = self._settings.load_players_from_CSV(filename)
        self._set_available_teams()

    def load_players(self, players):
        """
        Manually loads player to optimizer
        :type players: List[Player]
        """
        self._players = players
        self._set_available_teams()

    def _set_available_teams(self):
        """
        Evaluate all available teams.
        """
        self._available_teams = set([p.team for p in self._players])

    def remove_player(self, player):
        """
        Remove player from list for selecting players for lineup.
        :type player: Player
        """
        self._removed_players.append(player)

    def restore_player(self, player):
        """
        Restore removed player.
        :type player: Player
        """
        try:
            self._removed_players.remove(player)
        except ValueError:
            pass

    def _add_to_lineup(self, player):
        """
        Adding player to lineup without checks
        :type player: Player
        """
        self._lineup.append(player)
        self._total_players -= 1
        self._budget -= player.salary
        if self._min_salary:
            self._min_salary -= player.salary

        if self._max_salary:
            self._max_salary -= player.salary

    def find_players(self, name):
        """
        Return list of players with similar name.
        :param name: str
        :return: List[Player]
        """
        players = self.players
        possibilities = [(player, ratio(name, player.full_name)) for player in players]
        possibilities = filter(lambda pos: pos[1] >= self._search_threshold, possibilities)
        players = sorted(possibilities, key=lambda pos: -pos[1])
        return list(map(lambda p: p[0], players))

    def get_player_by_name(self, name):
        """
        Return closest player with similar name or None.
        :param name: str
        :return: Player
        """
        players = self.find_players(name)
        return players[0] if players else None

    def get_available_teams(self):
        return self._available_teams

    def get_total_players(self):
        return self._total_players

    def get_max_from_one_team(self):
        return self._settings.max_from_one_team

    def get_player_by_id(self, id):
        """
        Return closest player with similar name or None.
        :param name: str
        :return: Player
        """
        players = [player for player in self.players if player.id == id]
        return players[0] if players else None

    def _recalculate_positions(self, players):
        """
        Realculates available positions for optimizer with locked specified players.
        Return dict with positions for optimizer and number of placed players.
        :type players: List[Player]
        :return: Dict, int
        """
        positions = deepcopy(self._init_positions)
        players.sort(key=lambda p: len(p.positions))
        total_added = 0
        for player in players:
            is_added = False
            changed_positions = []
            for position, places in positions.items():
                if not list_intersection(player.positions, position):
                    continue
                if not places.max and list(player.positions) == list(position):
                    is_added = False
                    break
                is_added = True
                changed_positions.append(position)
            if is_added:
                total_added += 1
                [positions[position].add() for position in changed_positions]
        return positions, total_added

    def add_player_to_lineup(self, player):
        """
        Force adding specified player to lineup.
        Return true if player successfully added to lineup.
        :type player: Player
        """
        if player in self._lineup:
            raise LineupOptimizerException("This player already in your line up!")
        if not isinstance(player, Player):
            raise LineupOptimizerException("This function accept only Player objects!")
        if self._budget - player.salary < 0:
            raise LineupOptimizerException("Can't add this player to line up! Your team is over budget!")
        if self._total_players - 1 < 0:
            raise LineupOptimizerException("Can't add this player to line up! You already select all {} players!".
                                           format(len(self._lineup)))
        if self._max_from_one_team:
            from_same_team = len(list(filter(lambda p: p.team == player.team, self.lineup)))
            if from_same_team + 1 > self._max_from_one_team:
                raise LineupOptimizerException("You can't set more than {} players from one team.".
                                               format(self._max_from_one_team))
        players = self.lineup[:]
        players.append(player)
        positions, total_added = self._recalculate_positions(players)
        if total_added == len(players):
            self._add_to_lineup(player)
            self._positions = positions

            if self._site != Site.FANDUEL:
                for position, places in self._not_linked_positions.items():
                    if list_intersection(position, player.positions):
                        self._not_linked_positions[position].add()
        else:
            raise LineupOptimizerException("You're already select all {}'s".format("/".join(player.positions)))

    def remove_player_from_lineup(self, player):
        """
        Remove specified player from lineup.
        :type player: Player
        """
        if not isinstance(player, Player):
            raise LineupOptimizerException("This function accept only Player objects!")
        try:
            self._lineup.remove(player)
            self._budget += player.salary
            self._total_players += 1
            if self._site != Site.FANDUEL:
                for position, places in self._positions.items():
                    if list_intersection(position, player.positions):
                        self._positions[position].remove()
                for position, places in self._not_linked_positions.items():
                    if list_intersection(position, player.positions):
                        self._not_linked_positions[position].remove()
        except ValueError:
            raise LineupOptimizerException("Player not in line up!")

    def _validate_optimizer_params(self, teams=None, positions=None):
        """
        Validate passed to optimizer parameters.
        :type teams: dict[str, int]
        :type positions: dict[str, int]
        :return: processed teams and positions
        """

        # check teams parameter
       # if teams:
       #     if not isinstance(teams, dict) or not all([isinstance(team, str) for team in teams.keys()]) or \
        #            not all([isinstance(num_of_players, int) for num_of_players in teams.values()]):
         #       raise LineupOptimizerException("Teams parameter must be dict where key is team name and value is number"
         #                                      " of players from specified team.")
        #    teams = {team.upper(): num_of_players for team, num_of_players in teams.items()}
        #    for team, num_of_players in teams.items():
        #        if team not in self._available_teams:
        #            raise LineupOptimizerIncorrectTeamName("{} is incorrect team name.".format(team))
        #        if self._max_from_one_team and num_of_players > self._max_from_one_team:
        #            raise LineupOptimizerException("You can't set more than {} players from one team.".
        #                                           format(self._max_from_one_team))


        # check positions parameter
        if positions:
            if not isinstance(positions, dict) or \
                    not all([isinstance(position, str) for position in positions.keys()]) or \
                    not all([isinstance(num_of_players, int) for num_of_players in positions.values()]):
                raise LineupOptimizerException("Positions parameter must be dict where key is position name and value "
                                               "is number of players from specified position.")
            positions = {position.upper(): num_of_players for position, num_of_players in positions.items()}
            for pos, val in positions.items():
                available_places = self._positions[(pos,)].optional
                if val > self._positions[(pos,)].optional:
                    raise LineupOptimizerException("Max available places for position {} is {}. Got {} ".
                                                   format(pos, available_places, val))
                if (pos,) not in self._available_positions:
                    raise LineupOptimizerIncorrectPositionName("{} is incorrect position name.".format(pos))
        else:
            positions = {}
        return teams, positions

    def do_profile(follow=[]):
        def inner(func):
            def profiled_func(*args, **kwargs):
                try:
                    profiler = LineProfiler()
                    profiler.add_function(func)
                    for f in follow:
                        profiler.add_function(f)
                    profiler.enable_by_count()
                    return func(*args, **kwargs)
                finally:
                    profiler.print_stats()
            return profiled_func
        return inner

    #@do_profile(follow=[])
    def optimize(self):
        """
        Select optimal lineup from players list.
        This method uses Mixed Integer Linear Programming method for evaluating best starting lineup.
        It"s return generator. If you don"t specify n it will return generator with all possible lineups started
        from highest fppg to lowest fppg.
        :rtype: List[Lineup]
        """

        # validate positions and teams
        # teams, positions = self._validate_optimizer_params(self._teamConstraints, self._positionConstraints)

        locked_players = self._lineup[:]
        previous_lineup = []
        players = [player for player in self._players
                   if player not in self._removed_players and player not in self._lineup
                   and isinstance(player, Player) and player.max_exposure != 0.0 and
                   not (self._include_injured and player.is_injured)]

        # MLB no batters vs opp pitchers
        batters_by_team = defaultdict(list)
        pitchers = []
        #if self._sport == Sport.BASEBALL:
        if self._sport == Sport.BASEBALL or self._no_batters_vs_opp_pitchers:
            for pl in players:
                if pl.positions[0] != 'P':
                    batters_by_team[pl.team].append(pl)
                else:
                    pitchers.append(pl)

        # nfl stacking
        qbs = []
        receivers_by_team = defaultdict(list)
        if self._qb_wr_te_stack or self._qb_wr_stack or self._qb_te_stack:
            for pl in players:
                if pl.positions[0] == 'QB':
                    qbs.append(pl)
                else:
                    if self._qb_wr_te_stack:
                        if 'WR' in pl.positions or 'TE' in pl.positions:
                            receivers_by_team[pl.team].append(pl)
                    elif self._qb_wr_stack:
                        if 'WR' in pl.positions:
                            receivers_by_team[pl.team].append(pl)
                    elif self._qb_te_stack:
                        if 'TE' in pl.positions:
                            receivers_by_team[pl.team].append(pl)

        defenses = []
        rbs_by_team = defaultdict(list)
        opp_players = defaultdict(list)
        if self._rb_d_stack or self._no_def_vs_opp_players:
            for pl in players:
                if pl.positions[0] == 'D' or pl.positions[0] == 'DST':
                    defenses.append(pl)
                else:
                    if self._rb_d_stack and 'RB' in pl.positions:
                        rbs_by_team[pl.team].append(pl)
                    if self._no_def_vs_opp_players:
                        opp_players[pl.team].append(pl)

        rb_k = defaultdict(list)
        if self._no_qb_rb_k_same_team:
            for pl in players:
                if pl.positions[0] == 'QB':
                    if not qbs:
                        qbs.append(pl)
                elif 'RB' in pl.positions or 'K' in pl.positions:
                    rb_k[pl.team].append(pl)

        tight_ends = []
        rb_wr_k = defaultdict(list)
        if self._no_rb_wr_te_k_same_team:
            for pl in players:
                if pl.positions[0] == 'TE':
                    tight_ends.append(pl)
                elif 'RB' in pl.positions or 'WR' in pl.positions or 'K' in pl.positions:
                    rb_wr_k[pl.team].append(pl)

        current_max_points = 10000000
        counter = 0

        all_lineups = []
        diff_lineups = []
        ret_lineups = []

        if self._threads:
            print ("Threads " + str(self._threads))

        if self._message:
            print ("Message " + str(self._message))

        #LpSolverDefault.keepFiles = 1

        if self._solver and self._solver == 'CBC' and self._threads and self._threads > 0:
            LpSolverDefault.threads = self._threads

        if self._solver and self._solver == 'CBC' and self._message and self._message == 1:
            LpSolverDefault.msg = 1

        while self._num_of_lineups > counter:
            print (counter)
            if counter == 65:
                test11 = 1

            #start = time.time()
            prob = LpProblem("DFS", LpMaximize)

            x = LpVariable.dicts(
                "table", players,
                lowBound=0,
                upBound=1,
                cat=LpInteger
            )

            # add randomnes to the lineups
            if self._randomness:
                if previous_lineup:
                    for player in previous_lineup.players:
                        player.deviated_fppg = player.deviated_fppg * (1 + (-1 ) * uniform(self._min_deviation, self._max_deviation))
                else:
                    for player in players:
                        player.deviated_fppg = player.fppg

                # Goal => maximaze sum of fps
                prob += lpSum([player.deviated_fppg * x[player] for player in players])
            else:
                # Goal => maximaze sum of fps
                prob += lpSum([player.fppg * x[player] for player in players])
                if self._number_of_unique_players is None:
                    prob += lpSum([player.fppg * x[player] for player in players]) <= current_max_points

            # budget constraint
            if self._max_salary:
                prob += lpSum([player.salary * x[player] for player in players]) <= self._max_salary
            else:
                prob += lpSum([player.salary * x[player] for player in players]) <= self.budget

            if self._min_salary:
                prob += lpSum([player.salary * x[player] for player in players]) >= self._min_salary

            prob += lpSum([x[player] for player in players]) == self._total_players

            # set position constraints. Loop through all positions which are set in optimizer and add all players,
            # which have that position in a list of their positions, to constraint
            for position, places in self._positions.items():
                if self._sport == Sport.BASEBALL:
                    if position[0] != 'P' and self._site != Site.FANDUEL:
                        prob += lpSum([x[player] for player in players if
                                   any([player_position in position for player_position in player.positions])
                                   ]) >= places.min
                    else:
                        prob += lpSum([x[player] for player in players if
                                       any([player_position in position for player_position in player.positions])
                                       ]) == places.min
                elif self._sport == Sport.FOOTBALL or self._sport == Sport.BASKETBALL:
                    if len(position) == 3:
                        continue

                    if self._site != Site.FANDUEL and position[0] != 'QB' and position[0] != 'DST':
                        prob += lpSum([x[player] for player in players if
                                       any([player_position in position for player_position in player.positions])
                                       ]) >= places.min
                    else:
                        prob += lpSum([x[player] for player in players if
                                       any([player_position in position for player_position in player.positions])
                                       ]) == places.min


            # only for cases when there are multiple positions for player (dk MLB, NBA)
            if self._site == Site.DRAFTKINGS and (self._sport == Sport.BASEBALL or self._sport == Sport.BASKETBALL):
                # set constraints for all position combinations
                for position, places in self._not_linked_positions.items():
                    if 'P' in position:
                        continue
                    prob += lpSum([x[player] for player in players if
                                   any([player_position in position for player_position in player.positions])
                                   ]) >= places.min

            # avoid batters from pitcher opponent team
            if self._no_batters_vs_opp_pitchers:
                for pitcher in pitchers:
                    if pitcher:
                        prob += lpSum([x[pl] for pl in batters_by_team[pitcher.opponent]]) <= ((x[pitcher] - 1) * (-self._max_from_one_team))


            # stacks with qb
            if self._qb_wr_te_stack or self._qb_wr_stack or self._qb_te_stack:
                for qb in qbs:
                    if qb:
                        prob += lpSum([x[pl] for pl in receivers_by_team[qb.team]]) >= x[qb]

            # stacks with defense
            if self._rb_d_stack:
                for dst in defenses:
                    if dst:
                        prob += lpSum([x[pl] for pl in rbs_by_team[dst.team]]) >= x[dst]

            # no defense vs opp
            if self._no_def_vs_opp_players:
                for dst in defenses:
                    if dst:
                        prob += lpSum([x[pl] for pl in opp_players[dst.opponent]]) <= ((x[dst] - 1) * (-self._max_from_one_team))

            # no qb, rb, k, from same team
            if self._no_qb_rb_k_same_team:
                for qb in qbs:
                    if qb:
                        prob += lpSum([x[pl] for pl in rb_k[qb.team]]) <= (1 + (x[qb] - 1) * (-self._max_from_one_team + 1))

            # no rb, wr, te, k from same team
            if self._no_rb_wr_te_k_same_team:
                for te in tight_ends:
                    if te:
                        prob += lpSum([x[pl] for pl in rb_wr_k[te.team]]) <= ((x[te] - 1) * (-self._max_from_one_team ))

            if self._teamConstraints is not None and self._sport == Sport.BASEBALL:
                for key, value in self._teamConstraints.items():
                    for item in value:
                        if item[0] == '==':
                            prob += lpSum([x[player] for player in batters_by_team[key]]) == item[1]

            #for key, value in batters_by_team.items():
                #for item in value:
            #   prob += lpSum((sum([x[pl1] for pl1 in value]) == 3)) == 1

            # print (prob)
            # set exact number of players from same team
            if self._teamConstraints is not None:
                for key, value in self._teamConstraints.items():
                    for item in value:
                        if item[0] == '=':
                            prob += lpSum([x[player] for player in players if player.team == key]) == item[1]
                        elif item[0] == '>=':
                            prob += lpSum([x[player] for player in players if player.team == key]) >= item[1]
                        elif item[0] == '<=':
                            prob += lpSum([x[player] for player in players if player.team == key]) <= item[1]

            # limit maximum number of players from each team
            if self._max_from_one_team:
                for team in self._available_teams:
                    prob += lpSum([x[player] for player in players if player.team == team]) <= self._max_from_one_team

            if self._number_of_unique_players is not None and all_lineups:
                for lin in all_lineups:
                    prob += lpSum([x[player] for player in lin.players]) <= self._total_players - self._number_of_unique_players

            if diff_lineups and self._number_of_unique_players is None:
                for lin in diff_lineups:
                    prob += lpSum([x[player] for player in lin.players if player in x]) <= self._total_players - 1

            #prob.solve(pulp.COIN_CMD(path="C:\\Users\\hariso.HSL\\Downloads\\COIN-OR-1.7.4-win32-msvc11\\COIN-OR\\win32-msvc11\\bin\\cbc.exe"))
            #prob.solve()
            #prob.solve(pulp.GLPK_CMD(path="C:\\Users\\hariso.HSL\\Downloads\\winglpk-4.63\\glpk-4.63\\w64\\glpsol.exe", msg=0))

            if self._solver and self._solver == 'CBC':
                prob.solve()
            elif self._solver and self._solver == 'COIN':
                prob.solve(pulp.COIN_CMD(msg=self._message, threads=self._threads))
            else:
                prob.solve(pulp.GLPK_CMD(msg=self._message))

            #if self._solver and self._solver == 'CBC':
            #    prob.solve()
            #elif self._solver and self._solver == 'COIN':
            #    prob.solve(pulp.COIN_CMD(path="C:\\Users\\hariso.HSL\\Downloads\\COIN-OR-1.7.4-win32-msvc11\\COIN-OR\\win32-msvc11\\bin\\cbc.exe", msg=self._message, threads=self._threads))
            #else:
            #    prob.solve(pulp.GLPK_CMD(path="C:\\Users\\hariso.HSL\\Downloads\\winglpk-4.63\\glpk-4.63\\w64\\glpsol.exe", msg=self._message))

            #print (prob.solver)
            #end = time.time()
            #print(end - start)
            #print (str(len(prob._variables)))
            if prob.status == 1:
                lineup_players = self._lineup[:]
                removePlayers = []
                for player in players:
                    if x[player].value() == 1.0:
                        lineup_players.append(player)
                        player.num_of_lineups += 1
                        exposure = player.max_exposure if player.max_exposure is not None else self._max_exposure
                        if exposure is not None and exposure <= player.num_of_lineups / self._num_of_lineups:
                            if player in players:
                                removePlayers.append(player)

                lineup = Lineup(lineup_players)
                all_lineups.append(lineup)
                try:
                    new_lineup = self.get_sorted_lineup(lineup)
                    ret_lineups.append(new_lineup)
                except LineupOptimizerInvalidNumberOfPlayersInPineup:
                    return ret_lineups;

                if previous_lineup and not self._randomness:
                    current_lineup_points = lineup.fantasy_points_projection
                    previous_lineup_points = previous_lineup.fantasy_points_projection
                    if previous_lineup_points != current_lineup_points:
                        current_max_points = previous_lineup_points - 0.01
                        diff_lineups = []
                        #diff_lineups.append(lineup)
                    else:
                        diff_lineups.append(lineup)
                elif not self._randomness:
                    diff_lineups.append(lineup)

                previous_lineup = lineup
                #yield lineup
                #all_lineups.append(lineup)
                if removePlayers:
                    for remPl in removePlayers:
                        if self._no_batters_vs_opp_pitchers:
                            if remPl.positions[0] == 'P':
                                pitchers.remove(remPl)
                            else:
                                batters_by_team[remPl.team].remove(remPl)
                        if self._qb_wr_te_stack or self._qb_te_stack or self._qb_wr_stack:
                            if remPl.positions[0] == 'QB':
                                qbs.remove(remPl)
                            elif remPl.positions[0] == 'WR' or remPl.positions[0] == 'TE':
                                receivers_by_team[remPl.team].remove(remPl)
                        if self._rb_d_stack:
                            if remPl.positions[0] == 'D' or remPl.positions[0] == 'DST':
                                defenses.remove(remPl)
                            elif remPl.positions[0] == 'RB':
                                rbs_by_team[remPl.team].remove(remPl)
                        players[players.index(remPl)].fppg = -1000.0
                        players[players.index(remPl)].deviated_fppg = -1000.0

                if self._randomness:
                    current_max_points = sum(player.deviated_fppg for player in lineup_players) - 0.01
                counter += 1
            else:
                return ret_lineups
                #raise LineupOptimizerException("Can't generate lineups")
        self._lineup = locked_players
        return ret_lineups

    def fanduel_football_sort_lineup(self, lineup):
        sortedLineup = [Player] * self._settings.get_total_players()
        rb_count = 0
        wr_count = 0

        new_lineup = deepcopy(lineup)
        for player in new_lineup.players:
            if player.positions[0] == 'QB':
                sortedLineup[0] = player
            elif player.positions[0] == 'RB':
                sortedLineup[1 + rb_count] = player;
                rb_count = rb_count + 1
            elif player.positions[0] == 'WR':
                sortedLineup[3 + wr_count] = player
                wr_count = wr_count + 1
            elif player.positions[0] == 'TE':
                sortedLineup[6] = player
            elif player.positions[0] == 'K':
                sortedLineup[7] = player
            elif player.positions[0] == 'D':
                sortedLineup[8] = player

        return Lineup(sortedLineup)

    def fanduel_baseball_sort_lineup(self, lineup):
        sortedLineup = [Player] * self._settings.get_total_players()
        of_count = 0
        new_lineup = deepcopy(lineup)
        for player in new_lineup.players:
            if 'P' in player.positions:
                sortedLineup[0] = player
            elif 'C' in player.positions:
                sortedLineup[1] = player;
            elif '1B' in player.positions:
                sortedLineup[2] = player
            elif '2B' in player.positions:
                sortedLineup[3] = player
            elif '3B' in player.positions:
                sortedLineup[4] = player
            elif 'SS' in player.positions:
                sortedLineup[5] = player
            elif 'OF' in player.positions:
                sortedLineup[6 + of_count] = player
                of_count = of_count + 1

        return Lineup(sortedLineup)

    def fanduel_basketball_sort_lineup(self, lineup):
        sortedLineup = [Player] * self._settings.get_total_players()
        pg_count = 0
        sg_count = 0
        sf_count = 0
        pf_count = 0

        new_lineup = deepcopy(lineup)
        for player in new_lineup.players:
            if 'PG' in player.positions:
                sortedLineup[0 + pg_count] = player
                pg_count = pg_count + 1
            elif 'SG' in player.positions:
                sortedLineup[2 + sg_count] = player;
                sg_count = sg_count + 1
            elif 'SF' in player.positions:
                sortedLineup[4 + sf_count] = player
                sf_count = sf_count + 1
            elif 'PF' in player.positions:
                sortedLineup[6 + pf_count] = player
                pf_count = pf_count + 1
            elif 'C' in player.positions:
                sortedLineup[8] = player

        return Lineup(sortedLineup)

    def draftkings_football_sort_lineup(self, lineup):
        sortedLineup = [Player] * self._settings.get_total_players()
        rb_count = 0
        wr_count = 0
        te_count = 0
        newLineup = deepcopy(lineup)

        for player in newLineup.players:
            if player.positions[0] == 'QB':
                sortedLineup[0] = player
            elif player.positions[0] == 'RB':
                if rb_count <= 1:
                    sortedLineup[1 + rb_count] = player;
                else:
                    sortedLineup[7] = player;
                rb_count = rb_count + 1
            elif player.positions[0] == 'WR':
                if wr_count <= 2:
                    sortedLineup[3 + wr_count] = player
                else:
                    sortedLineup[7] = player
                wr_count = wr_count + 1
            elif player.positions[0] == 'TE':
                if te_count < 1:
                    sortedLineup[6] = player
                else:
                    sortedLineup[7] = player
                te_count = te_count + 1
            elif player.positions[0] == 'DST':
                sortedLineup[8] = player

        sortedLineup[1].provider_position = 'RB'
        sortedLineup[2].provider_position = 'RB'
        sortedLineup[3].provider_position = 'WR'
        sortedLineup[4].provider_position = 'WR'
        sortedLineup[5].provider_position = 'WR'
        sortedLineup[6].provider_position = 'TE'
        sortedLineup[7].provider_position = 'FLEX'

        return Lineup(sortedLineup)

    def draftkings_baseball_sort_lineup(self, lineup):
        sortedLineup = [Player] * self._settings.get_total_players()
        positions = {'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1, 'OF': 3}
        current_count = {'C': [], '1B': [], '2B': [], '3B': [], 'SS': [], 'OF': []}
        ignore_positions = []

        p_count = 0
        of_count = 0

        new_lineup = deepcopy(lineup)
        for player in new_lineup.players:
            if 'P' in player.positions:
                sortedLineup[0 + p_count] = player
                p_count = p_count + 1
                continue
            if 'C' in player.positions:
                if len(player.positions) == 1:
                    sortedLineup[2] = player
                    positions['C'] = 0
                    current_count['C'] = []
                    ignore_positions.append('C')
                    continue
                if 'C' not in ignore_positions:
                    current_count['C'].append(player)
            if '1B' in player.positions:
                if len(player.positions) == 1:
                    sortedLineup[3] = player
                    positions['1B'] = 0
                    current_count['1B'] = []
                    ignore_positions.append('1B')
                    continue
                if '1B' not in ignore_positions:
                    current_count['1B'].append(player)
            if '2B' in player.positions:
                if len(player.positions) == 1:
                    sortedLineup[4] = player
                    positions['2B'] = 0
                    current_count['2B'] = []
                    ignore_positions.append('2B')
                    continue
                if '2B' not in ignore_positions:
                    current_count['2B'].append(player)
            if '3B' in player.positions:
                if len(player.positions) == 1:
                    sortedLineup[5] = player
                    positions['3B'] = 0
                    current_count['3B'] = []
                    ignore_positions.append('3B')
                    continue
                if '3B' not in ignore_positions:
                    current_count['3B'].append(player)
            if 'SS' in player.positions:
                if len(player.positions) == 1:
                    sortedLineup[6] = player
                    positions['SS'] = 0
                    current_count['SS'] = []
                    ignore_positions.append('SS')
                    continue
                if 'SS' not in ignore_positions:
                    current_count['SS'].append(player)
            if 'OF' in player.positions:
                if len(player.positions) == 1:
                    sortedLineup[7 + of_count] = player
                    of_count = of_count + 1
                    positions['OF'] = positions['OF'] - 1
                    if positions['OF'] <= 0:
                        current_count['OF'] = []
                        ignore_positions.append('OF')
                    continue
                if 'OF' not in ignore_positions:
                    current_count['OF'].append(player)

        no_update = 0
        while True:
            handled = 0
            for position, pl in current_count.items():
                if len(pl) == 0 or positions[position] == 0:
                    continue

                if position == 'C' and len(pl) == positions['C']:
                    sortedLineup[2] = pl[0]
                    positions['C'] = 0
                    pp = pl[0]
                    handled = handled + 1
                    for pos in pp.positions:
                        if current_count[pos]:
                            ind = current_count[pos].index(pp)
                            del current_count[pos][ind]
                    current_count[position] = []
                elif position == '1B' and len(pl) == positions['1B']:
                    sortedLineup[3] = pl[0]
                    positions['1B'] = 0
                    pp = pl[0]
                    handled = handled + 1
                    for pos in pp.positions:
                        if current_count[pos]:
                            ind = current_count[pos].index(pp)
                            del current_count[pos][ind]
                    current_count[position] = []
                elif position == '2B' and len(pl) == positions['2B']:
                    sortedLineup[4] = pl[0]
                    positions['2B'] = 0
                    pp = pl[0]
                    handled = handled + 1
                    for pos in pp.positions:
                        if current_count[pos]:
                            ind = current_count[pos].index(pp)
                            del current_count[pos][ind]
                    current_count[position] = []
                elif position == '3B' and len(pl) == positions['3B']:
                    sortedLineup[5] = pl[0]
                    positions['3B'] = 0
                    pp = pl[0]
                    handled = handled + 1
                    for pos in pp.positions:
                        if current_count[pos]:
                            ind = current_count[pos].index(pp)
                            del current_count[pos][ind]
                    current_count[position] = []
                elif position == 'SS' and len(pl) == positions['SS']:
                    sortedLineup[6] = pl[0]
                    positions['SS'] = 0
                    pp = pl[0]
                    handled = handled + 1
                    for pos in pp.positions:
                        if current_count[pos]:
                            ind = current_count[pos].index(pp)
                            del current_count[pos][ind]
                    current_count[position] = []
                elif position == 'OF' and len(pl) == positions['OF']:
                    for p in pl:
                        handled = handled + 1
                        sortedLineup[7 + of_count] = p
                        positions['OF'] = positions['OF'] - 1
                        of_count = of_count + 1
                        for pos in p.positions:
                            if pos != 'OF':
                                if current_count[pos]:
                                    ind = current_count[pos].index(p)
                                    del current_count[pos][ind]

                    for p in pl:
                        if current_count[position]:
                            try:
                                ind = current_count[position].index(p)
                                del current_count[position][ind]
                            except:
                                nothing = True

                    current_count[position] = []

            done = True
            for pos, cnt in positions.items():
                if cnt > 0:
                    done = False
                    break
            if done:
                break

            if handled == 0:
                for position, pl in current_count.items():
                    if position == 'OF' and len(pl) == 4 - of_count:
                        pl_pos = pl[0].positions
                        pos_tmp_cnt = len(pl_pos)
                        same_pos = True
                        for p in pl:
                            if len(p.positions) != pos_tmp_cnt:
                                same_pos = False
                                break
                            for pos in p.positions:
                                if pos not in pl[0].positions:
                                    same_pos = False
                                    break
                        if not same_pos:
                            no_update = no_update + 1
                            break

                        num_added = 0
                        for pos in pl[0].positions:
                            pos_loc = self.get_draftkings_baseball_index(pos, p_count, of_count)
                            if pos == 'OF':
                                of_count = of_count + 1
                            elif pos == 'P':
                                p_count = p_count + 1
                            sortedLineup[pos_loc] = pl[num_added]
                            num_added = num_added + 1
                            positions[pos] = positions[pos] - 1

                        for pos in pl_pos:
                            current_count[pos] = []

                    if len(pl) == 2 and len(pl[0].positions) == 2 and len(pl[1].positions) == 2:
                        equal_pos = True
                        for pos in pl[0].positions:
                            if pos not in pl[1].positions:
                                equal_pos = False
                                no_update = no_update + 1
                                break

                        if equal_pos:
                            pl_pos = pl[0].positions
                            pos1_loc = self.get_draftkings_baseball_index(pl_pos[0], p_count, of_count)
                            pos2_loc = self.get_draftkings_baseball_index(pl_pos[1], p_count, of_count)

                            sortedLineup[pos1_loc] = pl[0]
                            sortedLineup[pos2_loc] = pl[1]
                            positions[pl_pos[0]] = positions[pl_pos[0]] - 1
                            positions[pl_pos[1]] = positions[pl_pos[1]] - 1
                            if pl_pos == 'OF' or pl_pos == 'OF':
                                of_count = of_count + 1
                            if pl_pos == 'P' or pl_pos == 'P':
                                p_count = p_count + 1

                            current_count[pl_pos[0]] = []
                            current_count[pl_pos[1]] = []
                            break

            if no_update > 5:
                break

        sortedLineup[2].provider_position = 'C'
        sortedLineup[3].provider_position = '1B'
        sortedLineup[4].provider_position = '2B'
        sortedLineup[5].provider_position = '3B'
        sortedLineup[6].provider_position = 'SS'
        sortedLineup[7].provider_position = 'OF'
        sortedLineup[8].provider_position = 'OF'
        sortedLineup[9].provider_position = 'OF'

        return Lineup(sortedLineup)

    def get_draftkings_baseball_index(self, position, p_count, of_count):
        if position == 'P':
            return 0 + p_count
        if position == 'C':
            return 2
        if position == '1B':
            return 3
        if position == '2B':
            return 4
        if position == '3B':
            return 5
        if position == 'SS':
            return 6
        if position == 'OF':
            return 7 + of_count

    def draftkings_basketball_sort_lineup(self, lineup):
        sortedLineup = [Player] * self._settings.get_total_players()
        current_count = {'PG': [], 'SG': [], 'SF': [], 'PF': [], 'C': [], 'G': [], 'F': [], 'FLEX': []}
        positions = {'PG': 1, 'SG': 1, 'SF': 1, 'PF': 1, 'C': 1, 'G': 1, 'F': 1, 'FLEX': 1}
        pg_count = 0
        sg_count = 0
        sf_count = 0
        pf_count = 0
        c_count = 0
        g_count = 0
        f_count = 0
        flex_count = 0

        new_lineup = deepcopy(lineup)
        for player in new_lineup.players:
            if 'PG' in player.positions:
                if len(player.positions) == 1 and pg_count == 0:
                    sortedLineup[0] = player
                    positions['PG'] = 0
                    pg_count = pg_count + 1
                    continue
                elif pg_count == 0:
                    current_count['PG'].append(player)
            if 'SG' in player.positions:
                if len(player.positions) == 1 and sg_count == 0:
                    sortedLineup[1] = player
                    positions['SG'] = 0
                    sg_count = sg_count + 1
                    continue
                elif sg_count == 0:
                    current_count['SG'].append(player)
            if 'SF' in player.positions:
                if len(player.positions) == 1 and sf_count == 0:
                    sortedLineup[2] = player
                    positions['SF'] = 0
                    sf_count = sf_count + 1
                    continue
                elif sf_count == 0:
                    current_count['SF'].append(player)
            if 'PF' in player.positions:
                if len(player.positions) == 1 and pf_count == 0:
                    sortedLineup[3] = player
                    positions['PF'] = 0
                    pf_count = pf_count + 1
                    continue
                elif pf_count == 0:
                    current_count['PF'].append(player)
            if 'C' in player.positions:
                if len(player.positions) == 1 and c_count == 0:
                    positions['C'] = 0
                    sortedLineup[4] = player
                    c_count = c_count + 1
                    continue
                elif c_count == 0:
                    current_count['C'].append(player)

            if 'SF' in player.positions or 'PF' in player.positions:
                current_count['F'].append(player)
            if 'PG' in player.positions or 'SG' in player.positions:
                current_count['G'].append(player)

            current_count['FLEX'].append(player)

        handled_counter = 0

        while True:
            handled = 0
            for position, pl in current_count.items():
                if len(pl) == 0 or positions[position] == 0:
                    positions[position] = 0
                    current_count[position] = []
                    continue

                #for pos in positions:

                #if positions[pos] > 0 and pos != 'FLEX' and len(current_count[pos]) > 0:
                #        test2 = [o.id for o in current_count[pos]]
                #        filtered = [i for i in current_count['FLEX'] if i in current_count[pos]]
                #        test = ""

                if position == 'PG' and len(pl) == 1:
                    pp = pl[0]
                    if pg_count == 0:
                        sortedLineup[0] = pl[0]
                        pg_count = pg_count + 1
                        handled = handled + 1

                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                            ind = current_count['F'].index(pp)
                            del current_count['F'][ind]

                        positions[position] = 0
                        current_count['PG'] = []
                        ind = current_count['G'].index(pp)
                        del current_count['G'][ind]
                        if pp in current_count['FLEX']:
                            ind = current_count['FLEX'].index(pp)
                            del current_count['FLEX'][ind]
                elif position == 'SG' and len(pl) == 1:
                    pp = pl[0]
                    if sg_count == 0:
                        sortedLineup[1] = pl[0]
                        sg_count = sg_count + 1
                        handled = handled + 1
                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                            ind = current_count['F'].index(pp)
                            del current_count['F'][ind]

                        positions[position] = 0
                        current_count['SG'] = []
                        ind = current_count['G'].index(pp)
                        del current_count['G'][ind]
                        if pp in current_count['FLEX']:
                            ind = current_count['FLEX'].index(pp)
                            del current_count['FLEX'][ind]
                elif position == 'SF' and len(pl) == 1:
                    pp = pl[0]
                    if sf_count == 0:
                        sortedLineup[2] = pl[0]
                        sf_count = sf_count + 1
                        handled = handled + 1
                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        if ('PG' in pp.positions or 'SG' in pp.positions) and pp in current_count['G']:
                            ind = current_count['G'].index(pp)
                            del current_count['G'][ind]

                        positions[position] = 0
                        current_count['SF'] = []
                        ind = current_count['F'].index(pp)
                        del current_count['F'][ind]
                        if pp in current_count['FLEX']:
                            ind = current_count['FLEX'].index(pp)
                            del current_count['FLEX'][ind]
                elif position == 'PF' and len(pl) == 1:
                    pp = pl[0]
                    if pf_count == 0:
                        sortedLineup[3] = pl[0]
                        pf_count = pf_count + 1
                        handled = handled + 1
                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        if ('PG' in pp.positions or 'SG' in pp.positions) and current_count['G']:
                            ind = current_count['G'].index(pp)
                            del current_count['G'][ind]

                        positions[position] = 0
                        current_count['PF'] = []
                        ind = current_count['F'].index(pp)
                        del current_count['F'][ind]
                        if pp in current_count['FLEX']:
                            ind = current_count['FLEX'].index(pp)
                            del current_count['FLEX'][ind]
                elif position == 'C' and len(pl) == 1:
                    pp = pl[0]
                    if c_count == 0:
                        sortedLineup[4] = pl[0]
                        c_count = c_count + 1
                        handled = handled + 1
                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                            ind = current_count['F'].index(pp)
                            del current_count['F'][ind]

                        if ('PG' in pp.positions or 'SG' in pp.positions) and pp in current_count['G']:
                            ind = current_count['G'].index(pp)
                            del current_count['G'][ind]

                        positions[position] = 0
                        current_count['C'] = []
                        if pp in current_count['FLEX']:
                            ind = current_count['FLEX'].index(pp)
                            del current_count['FLEX'][ind]
                elif position == 'G' and len(pl) == 1:
                    pp = pl[0]
                    if g_count == 0:
                        sortedLineup[5] = pl[0]
                        g_count = g_count + 1
                        handled = handled + 1
                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                            ind = current_count['F'].index(pp)
                            del current_count['F'][ind]

                        positions[position] = 0
                        current_count['G'] = []
                        if pp in current_count['FLEX']:
                            ind = current_count['FLEX'].index(pp)
                            del current_count['FLEX'][ind]
                elif position == 'F' and len(pl) == 1:
                    pp = pl[0]
                    if f_count == 0:
                        sortedLineup[6] = pl[0]
                        f_count = f_count + 1
                        handled = handled + 1
                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        if ('PG' in pp.positions or 'SG' in pp.positions) and pp in current_count['G']:
                            ind = current_count['G'].index(pp)
                            del current_count['G'][ind]

                        positions[position] = 0
                        if pp in current_count['FLEX']:
                            ind = current_count['FLEX'].index(pp)
                            del current_count['FLEX'][ind]
                        current_count['F'] = []
                elif position == 'FLEX' and len(pl) == 1:
                    pp = pl[0]
                    if flex_count == 0:
                        sortedLineup[7] = pl[0]
                        flex_count = flex_count + 1
                        handled = handled + 1
                        for pos in pp.positions:
                            if pp in current_count[pos]:
                                ind = current_count[pos].index(pp)
                                del current_count[pos][ind]

                        positions[position] = 0
                        current_count['FLEX'] = []

            if pg_count == 1 and sg_count == 1 and sf_count == 1 and pf_count == 1 and g_count == 1 and f_count == 1 and flex_count == 1:
                break

            if len(current_count['FLEX']) > 0 and positions['FLEX'] != 0:
                for pl in current_count['FLEX']:
                    if len(pl.positions) == 1 and pl.positions[0] == 'C':
                        sortedLineup[7] = pl[0]
                        positions['FLEX'] = 0
                        current_count['FLEX'] = []
                        flex_count = flex_count + 1
                        handled = handled + 1
                        break


            if handled == 0:
                handled_counter = handled_counter + 1
                if handled_counter > 3:
                    raise LineupOptimizerInvalidNumberOfPlayersInPineup("Invalid lineup")
                else:
                    sortedPositions = sorted((current_count[key], key) for key in current_count)
                    counter = 0
                    found = 0
                    while counter < 2:
                        if found == 1:
                            handled_counter = 0
                            break

                        for pl, position in sortedPositions:
                            if positions[position] == 0 or position == 'FLEX' or (counter == 0 and (position == 'G' or position == 'F')):
                                continue
                            else:

                                if len(current_count[position]) == 0:
                                    raise LineupOptimizerInvalidNumberOfPlayersInPineup("Invalid lineup")

                                found = 1
                                if position == 'PG':
                                    pp = pl[0]
                                    if pg_count == 0:
                                        sortedLineup[0] = pl[0]
                                        pg_count = pg_count + 1

                                        for pos in pp.positions:
                                            if pp in current_count[pos]:
                                                ind = current_count[pos].index(pp)
                                                del current_count[pos][ind]

                                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                                            ind = current_count['F'].index(pp)
                                            del current_count['F'][ind]

                                        positions[position] = 0
                                        current_count['PG'] = []
                                        ind = current_count['G'].index(pp)
                                        del current_count['G'][ind]
                                        if pp in current_count['FLEX']:
                                            ind = current_count['FLEX'].index(pp)
                                            del current_count['FLEX'][ind]
                                elif position == 'SG':
                                    pp = pl[0]
                                    if sg_count == 0:
                                        sortedLineup[1] = pl[0]
                                        sg_count = sg_count + 1
                                        for pos in pp.positions:
                                            if pp in current_count[pos]:
                                                ind = current_count[pos].index(pp)
                                                del current_count[pos][ind]

                                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                                            ind = current_count['F'].index(pp)
                                            del current_count['F'][ind]

                                        positions[position] = 0
                                        current_count['SG'] = []
                                        ind = current_count['G'].index(pp)
                                        del current_count['G'][ind]
                                        if pp in current_count['FLEX']:
                                            ind = current_count['FLEX'].index(pp)
                                            del current_count['FLEX'][ind]
                                elif position == 'SF':
                                    pp = pl[0]
                                    if sf_count == 0:
                                        sortedLineup[2] = pl[0]
                                        sf_count = sf_count + 1
                                        for pos in pp.positions:
                                            if pp in current_count[pos]:
                                                ind = current_count[pos].index(pp)
                                                del current_count[pos][ind]

                                        if ('PG' in pp.positions or 'SG' in pp.positions) and pp in current_count['G']:
                                            ind = current_count['G'].index(pp)
                                            del current_count['G'][ind]

                                        positions[position] = 0
                                        current_count['SF'] = []
                                        ind = current_count['F'].index(pp)
                                        del current_count['F'][ind]
                                        if pp in current_count['FLEX']:
                                            ind = current_count['FLEX'].index(pp)
                                            del current_count['FLEX'][ind]
                                elif position == 'PF':
                                    pp = pl[0]
                                    if pf_count == 0:
                                        sortedLineup[3] = pl[0]
                                        pf_count = pf_count + 1
                                        for pos in pp.positions:
                                            if pp in current_count[pos]:
                                                ind = current_count[pos].index(pp)
                                                del current_count[pos][ind]

                                        if ('PG' in pp.positions or 'SG' in pp.positions) and pp in current_count['G']:
                                            ind = current_count['G'].index(pp)
                                            del current_count['G'][ind]

                                        positions[position] = 0
                                        current_count['PF'] = []
                                        ind = current_count['F'].index(pp)
                                        del current_count['F'][ind]
                                        if pp in current_count['FLEX']:
                                            ind = current_count['FLEX'].index(pp)
                                            del current_count['FLEX'][ind]
                                elif position == 'C':
                                    pp = pl[0]
                                    if c_count == 0:
                                        sortedLineup[4] = pl[0]
                                        c_count = c_count + 1
                                        for pos in pp.positions:
                                            if pp in current_count[pos]:
                                                ind = current_count[pos].index(pp)
                                                del current_count[pos][ind]

                                        if ('PG' in pp.positions or 'SG' in pp.positions) and pp in current_count['G']:
                                            ind = current_count['G'].index(pp)
                                            del current_count['G'][ind]

                                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                                            ind = current_count['F'].index(pp)
                                            del current_count['F'][ind]

                                        positions[position] = 0
                                        current_count['C'] = []
                                        if pp in current_count['FLEX']:
                                            ind = current_count['FLEX'].index(pp)
                                            del current_count['FLEX'][ind]
                                elif position == 'G':
                                    pp = pl[0]
                                    if g_count == 0:
                                        sortedLineup[5] = pl[0]
                                        g_count = g_count + 1
                                        for pos in pp.positions:
                                            if pp in current_count[pos]:
                                                ind = current_count[pos].index(pp)
                                                del current_count[pos][ind]

                                        if ('SF' in pp.positions or 'PF' in pp.positions) and pp in current_count['F']:
                                            ind = current_count['F'].index(pp)
                                            del current_count['F'][ind]

                                        positions[position] = 0
                                        current_count['G'] = []
                                        if pp in current_count['FLEX']:
                                            ind = current_count['FLEX'].index(pp)
                                            del current_count['FLEX'][ind]
                                elif position == 'F':
                                    pp = pl[0]
                                    if f_count == 0:
                                        sortedLineup[6] = pl[0]
                                        f_count = f_count + 1
                                        for pos in pp.positions:
                                            if pp in current_count[pos]:
                                                ind = current_count[pos].index(pp)
                                                del current_count[pos][ind]

                                        if ('PG' in pp.positions or 'SG' in pp.positions) and pp in current_count['G']:
                                            ind = current_count['G'].index(pp)
                                            del current_count['G'][ind]

                                        positions[position] = 0
                                        current_count['F'] = []
                                        if pp in current_count['FLEX']:
                                            ind = current_count['FLEX'].index(pp)
                                            del current_count['FLEX'][ind]

                                if found == 1:
                                    break

                        counter = counter + 1


            else:
                handled_counter = 0


        sortedLineup[0].provider_position = 'PG'
        sortedLineup[1].provider_position = 'SG'
        sortedLineup[2].provider_position = 'SF'
        sortedLineup[3].provider_position = 'PF'
        sortedLineup[4].provider_position = 'C'
        sortedLineup[5].provider_position = 'G'
        sortedLineup[6].provider_position = 'F'
        sortedLineup[7].provider_position = 'FLEX'

        return Lineup(sortedLineup)

    def get_sorted_lineup(self, lineup):
        if len(lineup.players) != self._settings.get_total_players():
            raise LineupOptimizerInvalidNumberOfPlayersInPineup("Invalid lineup")

        for pl in lineup.players:
            if pl.fppg == -1000.0:
                raise LineupOptimizerInvalidNumberOfPlayersInPineup("Invalid lineup, negative points")

        if self._site == Site.FANDUEL and self._sport == Sport.FOOTBALL:
            return self.fanduel_football_sort_lineup(lineup)
        elif self._site == Site.FANDUEL and self._sport == Sport.BASEBALL:
            return self.fanduel_baseball_sort_lineup(lineup)
        elif self._site == Site.DRAFTKINGS and self._sport == Sport.FOOTBALL:
            return self.draftkings_football_sort_lineup(lineup)
        elif self._site == Site.DRAFTKINGS and self._sport == Sport.BASEBALL:
            return self.draftkings_baseball_sort_lineup(lineup)
        elif self._site == Site.FANDUEL and self._sport == Sport.BASKETBALL:
            return self.fanduel_basketball_sort_lineup(lineup)
        elif self._site == Site.DRAFTKINGS and self._sport == Sport.BASKETBALL:
            return self.draftkings_basketball_sort_lineup(lineup)

        return lineup
