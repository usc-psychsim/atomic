import numpy as np
from psychsim.agent import Agent
from psychsim.helper_functions import get_true_model_name
from psychsim.probability import Distribution
from psychsim.pwl import VectorDistributionSet, makeTree, noChangeMatrix, equalRow, incrementMatrix, WORLD, actionKey, \
    makeFuture, dynamicsMatrix, thresholdRow, setToConstantMatrix, modelKey, rewardKey
from psychsim.world import World
from locations_no_pre import Directions
from model_learning.trajectory import TOP_LEVEL_STR

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

INIT_LOC = 'BH2'

VIC_AMT_FEATURE = 'vic_amt'
TIME_FEATURE = 't'
PHASE_FEATURE = 'phase'
CLEAN_AGENT_NAME = 'Mr. Clean'
OBSERVER_AGENT_NAME = 'Observer'

GREEN_STR = 'Green'
GOLD_STR = 'Gold'
WHITE_STR = 'White'
RED_STR = 'Red'
TRIAGE_COLORS = [GREEN_STR, GOLD_STR]
VIC_COLORS = [GREEN_STR, GOLD_STR, WHITE_STR, RED_STR]

END_STR = 'end'
NEAR_END_STR = 'near_end'
MIDDLE_STR = 'middle'
NEAR_MIDDLE_STR = 'near_middle'
START_STR = 'start'
MISSION_PHASES = [START_STR, NEAR_MIDDLE_STR, MIDDLE_STR, NEAR_END_STR, END_STR]
MISSION_PHASE_END_TIMES = [8, 16, 20, 30]  # [40, 50, 80, 100]


class SearchAndRescueWorld(World):
    player_agents = []
    observer_agents = {}

    def __init__(self, loc_neighbors, victims_locs, loc_coords=None, name='', xml=None,
                 state_type=VectorDistributionSet):
        super().__init__(xml, state_type)

        self.loc_neighbors = loc_neighbors
        self.victims_locs = victims_locs
        self.name = name

        # gets location and neighbor direction mappings
        self.all_locations = list(loc_neighbors.keys())
        self.locs_with_neighbors = [set() for _ in Directions.Names]
        self.locs_from_directions = [set() for _ in Directions.Names]
        for loc, neighbors in loc_neighbors.items():
            for direction, neighbor in neighbors.items():
                self.locs_with_neighbors[direction].add(loc)
                self.locs_from_directions[direction].add(neighbor)

        # gets location coordinates
        self.coordinates = None if loc_coords is None else np.array([loc_coords[loc] for loc in self.all_locations])

        # creates features for amount of victims of each type in each location
        self.victim_amount_features = {}
        for loc in self.all_locations:
            self.victim_amount_features[loc] = {}
            for color in VIC_COLORS:
                vic_feat = self.defineState(
                    WORLD, VIC_AMT_FEATURE + color + loc + self.name, int,
                    description='Amount of {} victims in {}'.format(color, loc))
                num_vics = self.victims_locs[loc].count(color) if loc in self.victims_locs else 0
                self.setFeature(vic_feat, num_vics)  # set ground-truth data
                self.victim_amount_features[loc][color] = vic_feat

        # time-related features
        self.time_feat = self.defineState(WORLD, TIME_FEATURE, int, hi=1000, description='The mission clock time')
        self.setFeature(self.time_feat, 0)
        self.phase_feat = self.defineState(WORLD, PHASE_FEATURE, list, MISSION_PHASES, description='The mission phase')
        self.setFeature(self.phase_feat, START_STR)

        # create internal agents
        self.clean_agent = self.addAgent(CLEAN_AGENT_NAME)

    def step(self, actions=None, state=None, real=True, select=False, keySubset=None,
             horizon=None, tiebreak=None, updateBeliefs=True, debug={}):

        top_level = False
        if TOP_LEVEL_STR in debug and debug[TOP_LEVEL_STR]:
            top_level = True
            del debug[TOP_LEVEL_STR]

        # performs normal PsychSim step
        step_ret = super().step(actions, state, real, select, keySubset, horizon, tiebreak, updateBeliefs, debug)

        if not top_level:
            return step_ret

        # # TODO update agents' beliefs / visibility over the victims
        # for agent in self.player_agents:
        #     cur_locs = self.getFeature(agent.location_feature)
        #     for loc in cur_locs.domain():  # consider all possible locations?
        #         for color in VIC_COLORS:
        #             vic_amount_feat = self.victim_amount_features[loc][color]
        #             model = self.getFeature(modelKey(agent.name), unique=True)
        #             agent.setBelief(vic_amount_feat, self.getFeature(vic_amount_feat), None)#model)

        return step_ret

    def add_observer_agent(self, agent, prior=None):
        """
        Adds an observer agent that continuously updates a distribution over agent models.
        :param Agent agent: the agent whose models the observer will be tracking.
        :param Distribution prior: the observer's prior distribution over possible agent models.
        :rtype: Agent
        :return:
        """
        # create observer agent
        observer = self.addAgent(OBSERVER_AGENT_NAME + agent.name)
        self.observer_agents[agent] = observer, prior
        return observer

    def prepare(self, reset_beliefs=True):
        """
        Utility method that prepares this world for simulation after all agents have been created.
        :param bool reset_beliefs: whether to reset the player agents' beliefs.
        :return:
        """
        self._create_cleaning_actions()
        self.setOrder([{agent.name for agent in self.player_agents}, {self.clean_agent.name}])
        self.dependency.computeGraph()

        if reset_beliefs:
            for agent in self.player_agents:
                if agent not in self.observer_agents:
                    continue

                # agents do not model themselves and see everything except true models and their reward
                observer, prior = self.observer_agents[agent]
                true_model = get_true_model_name(agent)
                agent.resetBelief(model=true_model, ignore={modelKey(observer.name)})
                agent.omega = [key for key in self.state.keys()
                               if key not in {rewardKey(agent.name), modelKey(observer.name)}]

                # observer has uniform prior distribution over possible agent models
                observer.resetBelief(ignore={modelKey(observer.name)})
                prior = prior if prior is not None else \
                    Distribution(
                        {name: 1. / (len(agent.models) - 1) for name in agent.models.keys() if name != true_model})
                prior.normalize()
                self.setMentalModel(observer.name, agent.name, prior)

                # observer sees everything except itself and agent's true model
                observer.omega = [key for key in self.state.keys()
                                  if key not in {modelKey(agent.name), modelKey(observer.name)}]

    def _create_cleaning_actions(self):

        # create single cleaning action
        action = self.clean_agent.addAction({'verb': 'clean' + self.name})

        # update time-related features
        self.setDynamics(self.time_feat, action, makeTree(incrementMatrix(self.time_feat, 1)))
        tree = {'if': thresholdRow(self.time_feat, MISSION_PHASE_END_TIMES),
                len(MISSION_PHASE_END_TIMES): setToConstantMatrix(self.phase_feat, MISSION_PHASES[-1])}
        for i, phase_time in enumerate(MISSION_PHASE_END_TIMES):
            tree[i] = setToConstantMatrix(self.phase_feat, MISSION_PHASES[i])
        self.setDynamics(self.phase_feat, action, makeTree(tree))

        is_death_time = equalRow(makeFuture(self.time_feat),
                                 MISSION_PHASE_END_TIMES[MISSION_PHASES.index(NEAR_MIDDLE_STR)])

        # iterates through all locations to update corresponding counters
        for i, loc in enumerate(self.all_locations):

            # update agents' visitation frequency
            for agent in self.player_agents:
                loc_freq_feat = agent.location_frequency_features[loc]
                tree = {'if': equalRow(agent.location_feature, loc),
                        True: incrementMatrix(loc_freq_feat, 1),
                        False: noChangeMatrix(loc_freq_feat)}
                self.setDynamics(loc_freq_feat, action, makeTree(tree))

            # RED VICTIMS:
            #   if death time is reached, copy amount of alive victims to counter
            red_vic_feat = self.victim_amount_features[loc][RED_STR]
            weighted_inc = {red_vic_feat: 1.}
            for color in TRIAGE_COLORS:
                vic_color_amount_feat = self.victim_amount_features[loc][color]
                weighted_inc[vic_color_amount_feat] = 1.
            tree = {'if': is_death_time,
                    True: dynamicsMatrix(red_vic_feat, weighted_inc),
                    False: noChangeMatrix(red_vic_feat)}
            self.setDynamics(red_vic_feat, action, makeTree(tree))

            # WHITE VICTIMS:
            #   if any agent is in this location, increment counter according to change/difference in amount of victims
            white_vic_feat = self.victim_amount_features[loc][WHITE_STR]
            white_vic_tree = noChangeMatrix(white_vic_feat)
            for agent in self.player_agents:
                weighted_inc = {white_vic_feat: 1.}
                for color in TRIAGE_COLORS:
                    vic_color_amount_feat = self.victim_amount_features[loc][color]
                    weighted_inc[vic_color_amount_feat] = 1.
                    weighted_inc[makeFuture(vic_color_amount_feat)] = -1.

                white_vic_tree = {'if': equalRow(agent.location_feature, loc),
                                  True: dynamicsMatrix(white_vic_feat, weighted_inc),
                                  False: white_vic_tree}

            self.setDynamics(white_vic_feat, action, makeTree(white_vic_tree))

            # GREEN and GOLD VICTIMS:
            #   if death time reached, zero-out alive victims of that color
            #   else if any agent performed triage in the current room, decrement number of victims of that color
            for color in TRIAGE_COLORS:
                color_vic_feat = self.victim_amount_features[loc][color]
                color_vic_tree = noChangeMatrix(color_vic_feat)
                for agent in self.player_agents:
                    color_vic_tree = {'if': equalRow(agent.location_feature, loc),
                                      True: {'if': equalRow(actionKey(agent.name), agent.triage_actions[color]),
                                             True: incrementMatrix(color_vic_feat, -1),
                                             False: color_vic_tree},
                                      False: color_vic_tree}

                color_vic_tree = {'if': is_death_time,
                                  True: setToConstantMatrix(color_vic_feat, 0),
                                  False: color_vic_tree}

                self.setDynamics(color_vic_feat, action, makeTree(color_vic_tree))
