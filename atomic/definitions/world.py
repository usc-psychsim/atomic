from psychsim.pwl import WORLD, VectorDistributionSet, makeTree, thresholdRow, setToConstantMatrix, incrementMatrix
from psychsim.world import World

# mission phases
TIME_FEATURE = 'seconds'
PHASE_FEATURE = 'phase'
END_STR = 'end'
NEAR_END_STR = 'near_end'
MIDDLE_STR = 'middle'
NEAR_MIDDLE_STR = 'near_middle'
START_STR = 'start'
MISSION_PHASES = [START_STR, NEAR_MIDDLE_STR, MIDDLE_STR, NEAR_END_STR, END_STR]
MISSION_PHASE_END_TIMES = [150, 300, 420, 540]


class SearchAndRescueWorld(World):

    def __init__(self, xml=None, stateType=VectorDistributionSet):
        """
        :param xml: Initialization argument, either an XML Element, or a filename
        :type xml: Node or str
        :param stateType: Class used for the world state
        """

        super().__init__(xml, stateType)
        self.time = self.defineState(WORLD, TIME_FEATURE, int, description='The mission clock time')
        self.setFeature(self.time, 0)

        self.phase = self.defineState(WORLD, PHASE_FEATURE, list, MISSION_PHASES, description='The mission phase')
        self.setFeature(self.phase, START_STR)

        self.set_phase_dynamics()

    def set_phase_dynamics(self):

        # updates mission phase
        tree = {'if': thresholdRow(self.time, MISSION_PHASE_END_TIMES),
                len(MISSION_PHASE_END_TIMES): setToConstantMatrix(self.phase, MISSION_PHASES[-1])}
        for i, phase_time in enumerate(MISSION_PHASE_END_TIMES):
            tree[i] = setToConstantMatrix(self.phase, MISSION_PHASES[i])
        self.setDynamics(self.phase, True, makeTree(tree))
