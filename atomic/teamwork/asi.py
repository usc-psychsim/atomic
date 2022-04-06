from psychsim.pwl.keys import stateKey
from psychsim.pwl.matrix import setToConstantMatrix
from psychsim.pwl.tree import makeTree
from psychsim.agent import Agent

import operator


class ASI(Agent):

    # Effects that interventions have on AC variables
    AC_effects = {'cheer': {'CMU_BEARD': {'anger': {'object': operator.lt},
                                          'anxiety': {'object': operator.lt}}}}
    # Probability assigned to effects outlined in the AC_effects table
    base_probability = {'expected': 0.5, 'null': 0.4, 'unexpected': 0.1}

    def __init__(self, world, config=None, name='ATOMIC'):
        super().__init__(name, world)

    def add_interventions(self, players):
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
                    self.addAction({'verb': 'report drop', 'object': player, 'about': other})

        # Recommend phase-sensitive plan
        # Associated state: Game phase
        for player in players:
            self.addAction({'verb': 'notify phase', 'object': player})
            
        # Prompt for coordination best practices
        # Associated state: Unassigned requests/goals
        for player in players:
            self.addAction({'verb': 'remind practices', 'object': player})

        # Spread workload
        # Associated state: workload of individual players
        for player in players:
            self.addAction({'verb': 'distribute workload', 'object': player})

    def add_dynamics(self, action):
        """
        Automatically add dynamics of action on AC variables
        """
        obj = action['object'] if action['object'] in self.world.agents else None
        for AC, effect_table in self.AC_effects.get(action['verb']).items():
            for feature, effects in effect_table.items():
                if obj:
                    var = stateKey(obj, f'{AC} {feature}')
                    if var in self.world.variables and 'object' in effects:
                        self.create_tree(var, action, effects['object'])

    def create_tree(self, var, action, effect):
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
        tree = makeTree(table)
        self.world.setDynamics(var, action, tree, codePtr=True)
        return tree


def make_asi(world, team_agent, players, config=None):
    agent = ASI(world, config)
    world.addAgent(agent)
    agent.add_interventions(players)
    return agent


class Team(Agent):
    def __init__(self, world, name='team'):
        super().__init__(name, world)

    def initialize_variables(self):
        for var in ['mission analysis', 'goal specification', 'strategy formulation', 
                    'monitor goal progress', 'systems monitoring', 'team monitoring backup', 
                    'coordination', 'conflict management', 'motivating', 'affect management']:
            self.world.defineState(self.name, var, list, lo=['lo', 'hi'])
            self.setState(var, 'lo')
