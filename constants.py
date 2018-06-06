class Site:
    DRAFTKINGS = 'DRAFTKINGS'
    FANDUEL = 'FANDUEL'

class Sport:
    FOOTBALL = 'NFL'
    BASEBALL = 'MLB'
    BASKETBALL = 'NBA'

class LIMITS:
    MAX_LINEUPS = 200

class JSON_SPEC:
    # general
    SITE = 'site'
    SPORT = 'sport'
    NUMBER_OF_LINEUPS = 'numberOfLineups'
    MIN_TOTAL_SALARY = 'minTotalSalary'
    MAX_TOTAL_SALARY = 'maxTotalSalary'
    VARIATION = 'variation'
    MAX_EXPOSURE = 'maxExposure'
    STACKING = 'stacking'
    TEAM_NAME = 'teamName'
    NUMBER_OF_PLAYERS = 'numberOfPlayers'

    # players
    PLAYERS = 'players'
    PLAYER_ID = 'id'
    PLAYER_FULL_NAME = 'fullName'
    PLAYER_POSITION = 'position'
    PLAYER_FPPG = 'fppg'
    PLAYER_SALARY = 'salary'
    PLAYER_TEAM = 'team'
    PLAYER_OPPONENT = 'opponent'
    PLAYER_INJURED = 'injured'
    PLAYER_MAX_EXPOSURE = 'maxExposure'
    PLAYER_FORCE = 'force'
    PLAYER_EXCLUDE = 'exclude'

    # mlb
    NO_BATTERS_VS_PITCHERS = 'noBattersVsPitchers'

    # advanced
    MIN_MAX_PLAYERS_FROM_TEAM = 'minMaxPlayersFromTeam'
    MIN_PLAYERS = 'minPlayers'
    MAX_PLAYERS = 'maxPlayers'
    NUMBER_OF_UNIQUE_PLAYERS = 'numberOfUniquePlayers'

    # nfl
    STACK_TYPE = 'stackType'
    STACK_TEAMS = 'stackTeams'
    STACK_QB_WR = 'QB_WR'
    STACK_QB_TE = 'QB_TE'
    STACK_QB_WR_TE = 'QB_WR_TE'
    STACK_RB_D = 'RB_D'
    NO_QB_RB_K_FROM_TEAM = 'no_qb_rb_k_from_team'
    NO_RB_WR_TE_K = 'no_rb_wr_te_k_from_team'
    NO_DEF_VS_OPP_PLAYERS = 'no_def_vs_opp_players'

    SOLVER = 'solver'
    MESSAGE = 'message'
    THREADS = 'thrads'
