__version__ = "1.1.1"

from .player import Player
from .exceptions import LineupOptimizerException, LineupOptimizerIncorrectTeamName, \
    LineupOptimizerIncorrectPositionName, OptimizerParsingException, InvalidSiteSpecified, InvalidSportSpecified, ListOfPlayersIsEmpty
from .lineup_optimizer import LineupOptimizer
from .lineup import Lineup
from .settings import FanDuelFootballSettings, FanDuelBaseballSettings, FanDuelBasketballSettings, \
    DraftKingsFootballSettings, DraftKingsBaseballSettings, DraftKingsBasketballSettings
from .constants import *

settings_mapping = {
    Site.DRAFTKINGS: {
        Sport.FOOTBALL: DraftKingsFootballSettings,
        Sport.BASEBALL: DraftKingsBaseballSettings,
        Sport.BASKETBALL: DraftKingsBasketballSettings,

    },
    Site.FANDUEL: {
        Sport.FOOTBALL: FanDuelFootballSettings,
        Sport.BASEBALL: FanDuelBaseballSettings,
        Sport.BASKETBALL: FanDuelBasketballSettings,
    },
}

sites = [Site.FANDUEL,Site.DRAFTKINGS]
sports = [Sport.BASEBALL, Sport.FOOTBALL, Sport.BASKETBALL]

def get_optimizer(site, sport):
    try:
        return LineupOptimizer(settings_mapping[site][sport])
    except KeyError:
        raise NotImplementedError

def get_optimizer(jsonSpec):

    if JSON_SPEC.SITE not in jsonSpec or jsonSpec[JSON_SPEC.SITE] not in sites:
        raise InvalidSiteSpecified("Site specified in spec is invalid!!!")

    if JSON_SPEC.SPORT not in jsonSpec or jsonSpec[JSON_SPEC.SPORT] not in sports:
        raise InvalidSportSpecified("Sport specified in spec is invalid!!!")

    site = jsonSpec[JSON_SPEC.SITE]
    sport = jsonSpec[JSON_SPEC.SPORT]
    settings = settings_mapping[site][sport]
    optimizer = LineupOptimizer(settings_mapping[site][sport])
    players_list = []

    if JSON_SPEC.PLAYERS in jsonSpec:
        players = jsonSpec[JSON_SPEC.PLAYERS]

        for player in players:
            if JSON_SPEC.PLAYER_ID in player and player[JSON_SPEC.PLAYER_ID] and JSON_SPEC.PLAYER_FULL_NAME in player and \
                player[JSON_SPEC.PLAYER_FULL_NAME] and JSON_SPEC.PLAYER_POSITION in player and player[JSON_SPEC.PLAYER_POSITION] and \
                JSON_SPEC.PLAYER_FPPG in player and player[JSON_SPEC.PLAYER_FPPG] and \
                    (isinstance(player[JSON_SPEC.PLAYER_FPPG], float) or isinstance(player[JSON_SPEC.PLAYER_FPPG], int)) and \
                JSON_SPEC.PLAYER_SALARY in player and player[JSON_SPEC.PLAYER_SALARY] and isinstance(player[JSON_SPEC.PLAYER_SALARY], int) and \
                player[JSON_SPEC.PLAYER_SALARY] > 0 and JSON_SPEC.PLAYER_TEAM in player and player[JSON_SPEC.PLAYER_TEAM] and \
                JSON_SPEC.PLAYER_OPPONENT in player and player[JSON_SPEC.PLAYER_OPPONENT]:
                id = player[JSON_SPEC.PLAYER_ID]
                full_name = player[JSON_SPEC.PLAYER_FULL_NAME]
                positions_string = player[JSON_SPEC.PLAYER_POSITION]
                positions = []
                if '/' in positions_string:
                    positions = positions_string.split('/')
                else:
                    positions.append(positions_string)

                fps = player[JSON_SPEC.PLAYER_FPPG]
                salary = player[JSON_SPEC.PLAYER_SALARY]
                team = player[JSON_SPEC.PLAYER_TEAM].upper()
                opponent = player[JSON_SPEC.PLAYER_OPPONENT].upper()
                is_injured = False
                excluded = False
                force = False
                max_exposure = None
                if JSON_SPEC.PLAYER_INJURED in player and player[JSON_SPEC.PLAYER_INJURED] and isinstance(player[JSON_SPEC.PLAYER_INJURED], bool):
                    is_injured = player[JSON_SPEC.PLAYER_INJURED]
                if JSON_SPEC.PLAYER_FORCE in player and player[JSON_SPEC.PLAYER_FORCE] and isinstance(player[JSON_SPEC.PLAYER_FORCE], bool):
                    force = player[JSON_SPEC.PLAYER_FORCE]
                if JSON_SPEC.PLAYER_EXCLUDE in player and player[JSON_SPEC.PLAYER_EXCLUDE] and isinstance(player[JSON_SPEC.PLAYER_EXCLUDE], bool):
                    excluded = player[JSON_SPEC.PLAYER_EXCLUDE]
                if JSON_SPEC.PLAYER_MAX_EXPOSURE in player and player[JSON_SPEC.PLAYER_MAX_EXPOSURE] and (isinstance(player[JSON_SPEC.PLAYER_MAX_EXPOSURE], float) or
                    isinstance(player[JSON_SPEC.PLAYER_MAX_EXPOSURE], int)):
                    max_exposure = player[JSON_SPEC.PLAYER_MAX_EXPOSURE]
                    max_exposure = max_exposure / 100.0 if max_exposure and max_exposure > 1 else max_exposure

                pl = Player(id,full_name,positions, team, opponent, salary, fps, is_injured=is_injured, max_exposure=max_exposure,
                                force=force, exclude=excluded)
                if not excluded:
                    players_list.append(pl)

    if not players_list:
        raise ListOfPlayersIsEmpty("List of players is empty!!!")

    optimizer.load_players(players_list)
    optimizer._site = site
    optimizer._sport = sport
    optimizer._num_of_lineups = 1

    if JSON_SPEC.NUMBER_OF_LINEUPS in jsonSpec and isinstance(jsonSpec[JSON_SPEC.NUMBER_OF_LINEUPS], int) and \
                            0 < jsonSpec[JSON_SPEC.NUMBER_OF_LINEUPS] <= LIMITS.MAX_LINEUPS:
        optimizer._num_of_lineups = jsonSpec[JSON_SPEC.NUMBER_OF_LINEUPS]

    if JSON_SPEC.SOLVER in jsonSpec and (isinstance(jsonSpec[JSON_SPEC.SOLVER], str) or isinstance(jsonSpec[JSON_SPEC.SOLVER], unicode)):
        optimizer._solver = jsonSpec[JSON_SPEC.SOLVER]

    if JSON_SPEC.MESSAGE in jsonSpec and isinstance(jsonSpec[JSON_SPEC.MESSAGE], int) :
        optimizer._message = jsonSpec[JSON_SPEC.MESSAGE]

    if JSON_SPEC.THREADS in jsonSpec and isinstance(jsonSpec[JSON_SPEC.THREADS], int) :
        optimizer._threads = jsonSpec[JSON_SPEC.THREADS]

    if JSON_SPEC.MAX_EXPOSURE in jsonSpec and (isinstance(jsonSpec[JSON_SPEC.MAX_EXPOSURE], float) or
                                               isinstance(jsonSpec[JSON_SPEC.MAX_EXPOSURE], int)) and \
        0 < jsonSpec[JSON_SPEC.MAX_EXPOSURE] < 100:
        exposure = jsonSpec[JSON_SPEC.MAX_EXPOSURE]
        optimizer._max_exposure = exposure/100.0 if exposure and exposure > 1 else exposure

    if JSON_SPEC.MIN_TOTAL_SALARY in jsonSpec and isinstance(jsonSpec[JSON_SPEC.MIN_TOTAL_SALARY], int):
        min_total_salary = jsonSpec[JSON_SPEC.MIN_TOTAL_SALARY]
        optimizer._min_salary = min_total_salary if settings.budget/2 < min_total_salary <= settings.budget else None
        min_total_salary = optimizer._min_salary

    if JSON_SPEC.MAX_TOTAL_SALARY in jsonSpec and isinstance(jsonSpec[JSON_SPEC.MAX_TOTAL_SALARY], int):
        max_total_salary = jsonSpec[JSON_SPEC.MAX_TOTAL_SALARY]
        if min_total_salary is not None and min_total_salary > max_total_salary:
            max_total_salary = min_total_salary
        optimizer._max_salary = max_total_salary if settings.budget/2 < max_total_salary <= settings.budget else None

    if sport == Sport.BASEBALL and JSON_SPEC.NO_BATTERS_VS_PITCHERS in jsonSpec and isinstance(jsonSpec[JSON_SPEC.NO_BATTERS_VS_PITCHERS], bool):
        optimizer._no_batters_vs_opp_pitchers = jsonSpec[JSON_SPEC.NO_BATTERS_VS_PITCHERS]

    if sport == Sport.FOOTBALL and JSON_SPEC.NO_DEF_VS_OPP_PLAYERS in jsonSpec and isinstance(jsonSpec[JSON_SPEC.NO_DEF_VS_OPP_PLAYERS], bool):
        optimizer._no_def_vs_opp_players = jsonSpec[JSON_SPEC.NO_DEF_VS_OPP_PLAYERS]

    #if JSON_SPEC.NO_QB_RB_K_FROM_TEAM in jsonSpec and isinstance(jsonSpec[JSON_SPEC.NO_QB_RB_K_FROM_TEAM], bool):
    #    optimizer._no_qb_rb_k_same_team = jsonSpec[JSON_SPEC.NO_QB_RB_K_FROM_TEAM]

    #if JSON_SPEC.NO_RB_WR_TE_K in jsonSpec and isinstance(jsonSpec[JSON_SPEC.NO_RB_WR_TE_K], bool):
    #    optimizer._no_rb_wr_te_k_same_team = jsonSpec[JSON_SPEC.NO_RB_WR_TE_K]

    if JSON_SPEC.NUMBER_OF_UNIQUE_PLAYERS in jsonSpec and isinstance(jsonSpec[JSON_SPEC.NUMBER_OF_UNIQUE_PLAYERS], int):
        num_of_unique_players = jsonSpec[JSON_SPEC.NUMBER_OF_UNIQUE_PLAYERS]
        if 0 < num_of_unique_players <= optimizer.get_total_players():
            optimizer._number_of_unique_players = jsonSpec[JSON_SPEC.NUMBER_OF_UNIQUE_PLAYERS]

    if JSON_SPEC.VARIATION in jsonSpec and (isinstance(jsonSpec[JSON_SPEC.VARIATION], float) or isinstance(jsonSpec[JSON_SPEC.VARIATION], int)) and \
        jsonSpec[JSON_SPEC.VARIATION] > 0:
        variation = jsonSpec[JSON_SPEC.VARIATION]
        variation = variation/500.0 if variation > 1 else variation/5.0

        optimizer._min_deviation = variation/1.5
        optimizer._max_deviation = variation * 1.5
        optimizer._randomness = True

    remove_teams = []
    teamConstraints = {}
    if sport != Sport.BASKETBALL and JSON_SPEC.STACKING in jsonSpec:
        stackingJson = jsonSpec[JSON_SPEC.STACKING]
        if sport == Sport.BASEBALL:
            for item in stackingJson:
                if JSON_SPEC.TEAM_NAME in item and item[JSON_SPEC.TEAM_NAME] is not None and \
                    (isinstance(item[JSON_SPEC.TEAM_NAME], str) or isinstance(item[JSON_SPEC.TEAM_NAME], unicode)) and \
                    JSON_SPEC.NUMBER_OF_PLAYERS in item and item[JSON_SPEC.NUMBER_OF_PLAYERS] is not None and \
                    isinstance(item[JSON_SPEC.NUMBER_OF_PLAYERS], int):
                    team = item[JSON_SPEC.TEAM_NAME]
                    num_of_players = item[JSON_SPEC.NUMBER_OF_PLAYERS]
                    if team in optimizer.get_available_teams() and num_of_players <= optimizer.get_max_from_one_team():
                        if num_of_players > 0:
                            constraint = ['==', num_of_players]
                            teamConstraints[team] = [constraint]
                        else:
                            remove_teams.append(team)

        if sport == Sport.FOOTBALL:
            for item in stackingJson:
                use_teams = []
                if JSON_SPEC.STACK_TYPE in item and item[JSON_SPEC.STACK_TYPE] is not None and \
                        (item[JSON_SPEC.STACK_TYPE] == JSON_SPEC.STACK_QB_WR or item[JSON_SPEC.STACK_TYPE] == JSON_SPEC.STACK_RB_D or
                         item[JSON_SPEC.STACK_TYPE] == JSON_SPEC.STACK_QB_TE or item[JSON_SPEC.STACK_TYPE] == JSON_SPEC.STACK_QB_WR_TE):
                    stack_type = item[JSON_SPEC.STACK_TYPE]
                    if stack_type == JSON_SPEC.STACK_QB_WR or stack_type == JSON_SPEC.STACK_QB_TE or \
                            stack_type == JSON_SPEC.STACK_QB_WR_TE:
                        if stack_type == JSON_SPEC.STACK_QB_WR:
                            optimizer._qb_wr_stack = True
                        elif stack_type == JSON_SPEC.STACK_QB_TE:
                            optimizer._qb_te_stack = True
                        else:
                            optimizer._qb_wr_te_stack = True

                        if JSON_SPEC.STACK_TEAMS in item and item[JSON_SPEC.STACK_TEAMS] is not None and \
                            isinstance(item[JSON_SPEC.STACK_TEAMS], list):
                            stack_teams = item[JSON_SPEC.STACK_TEAMS]
                            for team in stack_teams:
                                if team is not None and team in optimizer.get_available_teams():
                                    use_teams.append(team)
                                if use_teams:
                                    pls = [pl for pl in optimizer.players if not (pl.positions[0] == 'QB' and pl.team not in use_teams)]
                                    optimizer.load_players(pls)
                    elif item[JSON_SPEC.STACK_TYPE] == JSON_SPEC.STACK_RB_D:
                        optimizer._rb_d_stack = True
                        if JSON_SPEC.STACK_TEAMS in item and item[JSON_SPEC.STACK_TEAMS] is not None and \
                                isinstance(item[JSON_SPEC.STACK_TEAMS], list):
                            stack_teams = item[JSON_SPEC.STACK_TEAMS]
                            for team in stack_teams:
                                if team is not None and team in optimizer.get_available_teams():
                                    use_teams.append(team)
                                if use_teams:
                                    pls = [pl for pl in optimizer.players if not ((pl.positions[0] == 'D' or pl.positions[0] == 'DST') and pl.team not in use_teams)]
                                    optimizer.load_players(pls)

    if JSON_SPEC.MIN_MAX_PLAYERS_FROM_TEAM in jsonSpec:
        minMaxPlayersFromTeam = jsonSpec[JSON_SPEC.MIN_MAX_PLAYERS_FROM_TEAM]
        for item in minMaxPlayersFromTeam:
            if JSON_SPEC.TEAM_NAME in item and item[JSON_SPEC.TEAM_NAME] is not None and \
                    (isinstance(item[JSON_SPEC.TEAM_NAME], str) or isinstance(item[JSON_SPEC.TEAM_NAME], unicode)):
                team = item[JSON_SPEC.TEAM_NAME]
                minPlayers = None
                maxPlayers = None
                if team in optimizer.get_available_teams() and team not in teamConstraints:
                    if JSON_SPEC.MIN_PLAYERS in item and item[JSON_SPEC.MIN_PLAYERS] is not None and isinstance(item[JSON_SPEC.MIN_PLAYERS], int):
                        minPlayers = item[JSON_SPEC.MIN_PLAYERS]
                        minPlayers = minPlayers if minPlayers <= optimizer.get_max_from_one_team() else optimizer.get_max_from_one_team()
                        #minPlayers = None if minPlayers > optimizer.get_max_from_one_team() else minPlayers
                    if JSON_SPEC.MAX_PLAYERS in item and item[JSON_SPEC.MAX_PLAYERS] is not None and isinstance(item[JSON_SPEC.MAX_PLAYERS], int):
                        maxPlayers = item[JSON_SPEC.MAX_PLAYERS]
                        maxPlayers = maxPlayers if maxPlayers <= optimizer.get_max_from_one_team() else optimizer.get_max_from_one_team()
                       # maxPlayers = None if maxPlayers > optimizer.get_max_from_one_team() else maxPlayers
                    if minPlayers is not None and maxPlayers is not None:
                        if minPlayers >= maxPlayers:
                            if minPlayers == 0:
                                remove_teams.append(team)
                            else:
                                teamConstraints[team] = [['=', minPlayers]]
                        else:
                            if maxPlayers == 0:
                                remove_teams.append(team)
                            elif minPlayers == 0:
                                teamConstraints[team] = [['<=', maxPlayers]]
                            else:
                                teamConstraints[team] = [['<=', maxPlayers], ['>=', minPlayers]]
                    elif minPlayers is None and maxPlayers is not None:
                        if maxPlayers == 0:
                            remove_teams.append(team)
                        else:
                            teamConstraints[team] = [['<=', maxPlayers]]
                    elif maxPlayers is None and minPlayers is not None:
                        if minPlayers > 0:
                            teamConstraints[team] = [['>=', minPlayers]]
    if remove_teams:
        pls = [pl for pl in optimizer.players if pl.team not in remove_teams]
        for team in remove_teams:
            optimizer.get_available_teams().remove(team)
        optimizer.load_players(pls)

    for pl in optimizer.players:
        if pl.force:
            pl.fppg = 1000.0 #optimizer.add_player_to_lineup(pl)

    if teamConstraints:
        optimizer._teamConstraints = teamConstraints

    return optimizer
