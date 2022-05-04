from string import Template

from psychsim.pwl.keys import stateKey, makeFuture
from psychsim.pwl.matrix import setToConstantMatrix, setTrueMatrix, setFalseMatrix
from psychsim.pwl.plane import equalRow, trueRow
from psychsim.pwl.tree import makeTree
from psychsim.reward import maximizeFeature, minimizeFeature
from psychsim.agent import Agent

from .interventions import interventions


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
        self.team = None
        self.interventions = {}

    def generate_message(self, action):
        if action == self.noop:
            return None
        else:
            template = interventions[action['verb']]['template']
            sub = dict(action.items())
            return template.substitute(sub)

    def add_noop(self, team):
        self.noop = self.addAction({'verb': 'do nothing'})
        for feature in team.processes:
            var = stateKey(team.name, feature)
            tree = {'if': trueRow(var), 
                    True: {'distribution': [(setTrueMatrix(var), 1-self.base_probability['unexpected']),
                                            (setFalseMatrix(var), self.base_probability['unexpected'])]},
                    False: {'distribution': [(setTrueMatrix(var), self.base_probability['unexpected']),
                                             (setFalseMatrix(var), 1-self.base_probability['unexpected'])]}}
            self.world.setDynamics(var, self.noop, makeTree(tree))

    def add_interventions(self, players, team):
        self.team = team
        self.add_noop(team)
        self.interventions[None] = {self.noop}
        for verb, table in interventions.items():
            # Extract NLG template
            if isinstance(table['template'], str):
                table['template'] = Template(table['template'])
            # Create flag for tracking whether we've already done this intervention
            flag = self.world.defineState(self.name, f'tried {verb}', bool)
            self.world.setFeature(flag, False)
            # Figure out whether this intervention targets a single player or the whole team
            obj = table.get('object', 'team')
            if obj == 'player':
                for player in players:
                    action = self.addAction({'verb': verb, 'object': player})
                    self.add_dynamics(action, flag)
                    tree = {'if': trueRow(flag), True: False, False: True}
                    if 'legal' in table:
                        tree[False] = table['legal']
                    self.setLegal(action, makeTree(tree))
            elif obj == 'team':
                action = self.addAction({'verb': verb})
                self.add_dynamics(action, flag)
                tree = {'if': trueRow(flag), True: False, False: True}
                if 'legal' in table:
                    tree[False] = table['legal']
                self.setLegal(action, makeTree(tree))
            else:
                raise NameError(f'Illegal object {obj} specified for intervention {verb}')
            if verb in self.interventions:
                self.interventions[verb].add(action)
            else:
                self.interventions[verb] = {action}

    def add_dynamics(self, action, flag=None):
        """
        Automatically add dynamics of action on AC variables
        """
        for feature, effect in interventions[action['verb']].get('effects', {}).items():
            var = stateKey(self.team.name, feature)
            tree = {'if': trueRow(var),
                    True: {'distribution': [(setTrueMatrix(var), 1-self.base_probability['unexpected']),
                                            (setFalseMatrix(var), self.base_probability['unexpected'])]},
                    False: {'distribution': [(setTrueMatrix(var), self.base_probability['expected']),
                                             (setFalseMatrix(var), 1-self.base_probability['expected'])]}}
            self.world.setDynamics(var, action, makeTree(tree))
        if flag is not None:
            self.world.setDynamics(flag, action, makeTree(setTrueMatrix(flag)))

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
    agent.setReward(minimizeFeature(stateKey(team_agent.name, 'cognitive load'), agent.name), 1)
    agent.setAttribute('horizon', 1)
    return agent


class Team(Agent):

    processes = [  # 'mission analysis', 
                   # 'goal specification', 
                   # 'strategy formulation', 
                   # 'monitor goal progress', 
                   'systems monitoring', 
                   'team monitoring', 
                   'coordination', 
                   # 'conflict management', 
                   'motivating', 
                   'affect management',
                   ]

    def __init__(self, world, name='team'):
        super().__init__(name, world)

    def initialize_variables(self):
        for var in self.processes:
            self.world.defineState(self.name, var, bool)
            self.setState(var, False)
        var = self.world.defineState(self.name, 'cognitive load', bool)
        self.setState('cognitive load', False)

    def initialize_effects(self, acs={}):
        self.noop = self.addAction({'verb': 'do nothing'})
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
