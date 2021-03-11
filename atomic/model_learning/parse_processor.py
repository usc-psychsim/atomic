from atomic.parsing import ParsingProcessor
from model_learning.trajectory import copy_world

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'


class TrajectoryParseProcessor(ParsingProcessor):
    """
    Simply keeps track of the world state and copies to a trajectory.
    """
    def __init__(self):
        super().__init__()
        self.trajectory = []
        self.prev_world = None

    def pre_step(self, world):
        self.prev_world = copy_world(world)

    def post_step(self, world, act):
        if act is not None:
            self.trajectory.append((self.prev_world, act))
