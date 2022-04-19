from psychsim.pwl.keys import stateKey, makeFuture
from psychsim.pwl.matrix import setToConstantMatrix
from psychsim.pwl.plane import equalRow
from psychsim.pwl.tree import makeTree
from psychsim.reward import maximizeFeature
from psychsim.agent import Agent


class ASI(Agent):

    # Probability assigned to effects outlined in the AC_effects table
    base_probability = {'expected': 0.5, 'null': 0.4, 'unexpected': 0.1}

    def __init__(self, world, acs={}, config=None, name='ATOMIC'):
        self.acs = acs
        self.config = config
        super().__init__(name, world)
        self.conditions = {}
        for AC in self.acs.values():
            self.conditions.update(AC.get_conditions())

    def add_interventions(self, players, team):
        # Inter-mission AAR prompt
        # Associated state: Descriptors from situation to highlight (implies descriptors of current situation are being maintained)

        # Cheerleading action
        for player in players:
            action = self.addAction({'verb': 'cheer', 'object': player})
            self.add_dynamics(action)

        # Report performance change
        # Associated state: Individual performance level, team leader
        for player in players:
            for other in players:
                if other != player:
                    action = self.addAction({'verb': 'report drop', 'object': player, 'about': other})
                    self.add_dynamics(action)

        # Recommend phase-sensitive plan
        # Associated state: Game phase
        for player in players:
            action = self.addAction({'verb': 'notify phase', 'object': player})
            self.add_dynamics(action)
            
        # Prompt for coordination best practices
        # Associated state: Unassigned requests/goals
        for player in players:
            action = self.addAction({'verb': 'remind practices', 'object': player})
            self.add_dynamics(action)

        # Spread workload
        # Associated state: workload of individual players
        for player in players:
            action = self.addAction({'verb': 'distribute workload', 'object': player})
            self.add_dynamics(action)

    def add_dynamics(self, action):
        """
        Automatically add dynamics of action on AC variables
        """
        obj = action['object'] if action['object'] in self.world.agents else None
        for AC_name, AC in self.acs.items():
            for feature, effects in AC.get_effects(action).items():
                if obj:
                    var = stateKey(obj, feature)
                    if var in self.world.variables and 'object' in effects:
                        self.create_tree(var, action, effects['object'])

    def create_tree(self, var, action, effect):
        # Create condition branch
        condition_vars = list(self.conditions.keys())
        total = sum([len(self.variables[var]['elements']) for var in condition_vars])
        table = {'if': equalRow(condition_vars, list(range(total+1)))}
        for condition_count in range(total+1):
            table[condition_count] = self.create_subtree(var, effect, (condition_count+1)/(total+2))
        tree = makeTree(table)
        self.world.setDynamics(var, action, tree, codePtr=True)
        return tree

    def create_subtree(self, var, effect, scale=1):
        if self.world.variables[var]['domain'] is list:
            domain = self.world.variables[var]['elements']
        else:
            raise TypeError(f'Unable to parse effects over {self.world.variables[var]["domain"]} variables')
        # Create tree
        table = {'case': var}
        for i, val_i in enumerate(domain):
            dist = []
            for j, val_j in enumerate(domain):
                if effect(j, i):
                    # Expected change
                    prob = self.base_probability['expected']/i
                elif i == j:
                    # No change, i.e., null effect
                    prob = self.base_probability['null']
                else:
                    # Unexpected change
                    prob = self.base_probability['unexpected']/(len(domain)-i-1)
                dist.append((setToConstantMatrix(var, val_j), prob))
            table[val_i] = {'distribution': dist}
        return table


def make_asi(world, team_agent, players, acs={}, config=None):
    agent = ASI(world, acs, config)
    world.addAgent(agent)
    agent.add_interventions(players, team_agent)
    for AC in acs.values():
        for var, weight in AC.get_ASI_reward().items():
            agent.setReward(maximizeFeature(var, agent.name), weight)
    return agent


class Team(Agent):

    processes = ['mission analysis', 'goal specification', 'strategy formulation', 
                 'monitor goal progress', 'systems monitoring', 'team monitoring backup', 
                 'coordination', 'conflict management', 'motivating', 'affect management']

    def __init__(self, world, name='team'):
        super().__init__(name, world)

    def initialize_variables(self):
        for var in self.processes:
            self.world.defineState(self.name, var, int, lo=0, hi=1)
            self.setState(var, 0)

    def initialize_effects(self, acs={}):
        # Identify AC variables that influence process variables
        conditions = {}
        for AC in acs.values():
            for var, table in AC.get_field('process').items():
                for process, effect in table.items():
                    try:
                        conditions[process][var] = effect
                    except KeyError:
                        conditions[process] = {var: effect}
        for process, table in conditions.items():
            key = stateKey(self.name, process)
            lo = hi = 0
            for var, effect in table.items():
                if effect < 0:
                    lo -= 1
                elif effect > 0:
                    hi += 1
            tree_table = {'if': equalRow({makeFuture(k): weight for k, weight in table.items()}, 
                                         list(range(lo, hi+1)))}
            for condition_count in range(lo, hi+1):
                prob_hi = (condition_count-lo+1)/(hi-lo+1)
                tree_table[condition_count] = {'if': equalRow(key, [0, 1]),
                                               0: {'distribution': [(setToConstantMatrix(key, 0), 0.5+(1-prob_hi)/2), 
                                                                    (setToConstantMatrix(key, 1), prob_hi/2)]},
                                               1: {'distribution': [(setToConstantMatrix(key, 0), (1-prob_hi)/2), 
                                                                    (setToConstantMatrix(key, 1), 0.5+prob_hi/2)]}}
            self.world.setDynamics(key, True, makeTree(tree_table))


def make_team(world):
    team = Team(world)
    team.initialize_variables()
    return team
