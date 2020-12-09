import logging
from model_learning.trajectory import copy_world
from atomic.parsing.parser import ProcessCSV

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'


class TrajectoryParser(ProcessCSV):
    def __init__(self, filename, maxDist=5, logger=logging):
        super().__init__(filename, maxDist, logger)
        self.trajectory = []
        self.prev_world = None
        self._player_name = None

    def pre_step(self, world):
        self.prev_world = copy_world(world)

    def post_step(self, world, act):
        if act is not None:
            self.trajectory.append((self.prev_world, act))
