class LineupOptimizerException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class LineupOptimizerIncorrectTeamName(LineupOptimizerException):
    pass


class LineupOptimizerIncorrectPositionName(LineupOptimizerException):
    pass

class LineupOptimizerInvalidNumberOfPlayersInPineup(LineupOptimizerException):
    pass

class OptimizerParsingException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class InvalidSportSpecified(OptimizerParsingException):
    pass

class InvalidSiteSpecified(OptimizerParsingException):
    pass

class ListOfPlayersIsEmpty(OptimizerParsingException):
    pass
