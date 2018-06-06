from __future__ import division


class Player(object):
    num_of_lineups = 0

    def __init__(self, id, full_name, positions, team, opponent, salary, fppg, is_injured=False, max_exposure=None, force=False, exclude=False):
        self.id = id
        self.full_name = full_name
        self.positions = positions
        self.team = team.upper()
        self.opponent = opponent.upper()
        self.salary = salary
        self.fppg = fppg
        self.is_injured = is_injured
        self._max_exposure = None
        self.max_exposure = max_exposure
        self.exclude = exclude
        self.force = force
        self.provider_position = positions[0]
        self.real_points = fppg

    def __str__(self):
        return "{}{}{}{}{}".format(
            "{:<30}".format(self.full_name),
            "{:<5}".format('/'.join(self.provider_position)),
            "{:<15}".format(self.team),
            "{:<15}".format(self.opponent),
            "{:<8}".format(str(round(self.real_points, 3))),
            "{:<10}".format(str(self.salary) + '$')
        )

    def jdefault(o):
        return o.__dict__

    @property
    def max_exposure(self):
        return self._max_exposure

    @max_exposure.setter
    def max_exposure(self, max_exposure):
        self._max_exposure = max_exposure / 100.0 if max_exposure and max_exposure > 1 else max_exposure

    #@property
    #def full_name(self):
    #    return "{} {}".format(self.first_name, self.last_name)

    @property
    def efficiency(self):
        return round(self.fppg / self.salary, 2)

    def __getitem__(self, index):
        return 0