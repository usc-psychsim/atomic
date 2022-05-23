import pandas
from string import Template

from psychsim.pwl.keys import stateKey, makeFuture, isStateKey, state2agent, state2feature, key2relation
from psychsim.pwl.matrix import setToConstantMatrix, setTrueMatrix, setFalseMatrix
from psychsim.pwl.plane import equalRow, trueRow
from psychsim.pwl.tree import makeTree
from psychsim.reward import maximizeFeature, minimizeFeature
from psychsim.probability import Distribution
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
        self.inactivity = 0
        self.belief_data = pandas.DataFrame()

    def generate_message(self, action, sub={}, trial=1):
        if action == self.noop:
            return None
        else:
            template = interventions[action['verb']]['template']
            if isinstance(template, list):
                template = template[trial-1]
            new_sub = dict(action.items())
            new_sub.update(sub)
            try:
                return template.substitute(new_sub)
            except KeyError:
                return None

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
            elif isinstance(table['template'], list) and isinstance(table['template'][0], str):
                table['template'] = [Template(t) for t in table['template']]
            # Create flag for tracking whether we've already done this intervention
            flag = self.world.defineState(self.name, f'tried {verb}', bool)
            self.world.setFeature(flag, False)
            valid = self.world.defineState(self.name, f'valid {verb}', bool)
            self.world.setFeature(valid, table.get('valid on start', False))
            # Figure out whether this intervention targets a single player or the whole team
            obj = table.get('object', 'team')
            if obj == 'player':
                for player in players:
                    action = self.addAction({'verb': verb, 'object': player})
                    self.add_dynamics(action, flag)
                    tree = {'if': trueRow(flag), True: False, 
                            False: {'if': trueRow(valid), True: True, False: False}}
                    if 'legal' in table:
                        tree[False][True] = table['legal']
                    self.setLegal(action, makeTree(tree))
            elif obj == 'team':
                action = self.addAction({'verb': verb})
                self.add_dynamics(action, flag)
                tree = {'if': trueRow(flag), True: False, 
                        False: {'if': trueRow(valid), True: True, False: False}}
                if 'legal' in table:
                    tree[False][True] = table['legal']
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

    def initialize_team_beliefs(self, prior=None):
        belief = self.create_belief_state()
        for feature in self.team.processes:
            key = stateKey(self.team.name, feature)
            if prior is None:
                self.world.setFeature(key, Distribution({True: 0.5, False: 0.5}), belief)
            else:
                self.world.setFeature(key, self.world.getFeature(key, prior), belief)

    def update_interventions(self, AC, delta):
        change = False
        influence = {}
        leadership = {}
        gap = {}
        noncompliance = set()
        for key, value in delta.items():
            for process, change in self.acs[AC.name].influences.get(key, {}).items():
                influence[process] = influence.get(process, 0) + change
            if isStateKey(key) and state2feature(key) == 'ac_gallup_ta2_gelp Leadership':
                leadership[state2agent(key)] = value
            elif key == stateKey(self.name, 'valid cheer'):
                if isinstance(value, dict):
                    self.world.intervention_args['cheer'].update(value)
                change = True
            elif AC.name == 'AC_CORNELL_TA2_TEAMTRUST':
                rel = key2relation(key)
                pair = (rel['subject'], rel['object'])
                if rel['relation'] == f'{AC.name}_compliance_overall':
                    if value < 0.01:
                        noncompliance.add(pair)
                    value = -value
                gap[pair] = gap.get(pair, 0) + value
            elif isStateKey(key) and state2feature(key) == 'ac_cmu_ta2_ted inaction_stand_s' and not self.world.planning:
                if value:
                    self.inactivity += 1
                else:
                    self.inactivity = 0
                if self.inactivity > 10:
                    self.setState('valid prompt activity', True, recurse=True)
                else:
                    self.setState('valid prompt activity', False, recurse=True)
            elif isStateKey(key) and state2feature(key) == 'AC_Rutgers_TA2_Utility wait_time':
                if value:
                    self.setState('valid reflect', True, recurse=True)
                    record = AC.last.to_dict('records')[0]
                    if len(self.world.intervention_args['reflect']) == 0 or record['wait_time'] > self.world.intervention_args['reflect']['wait_time']:
                        self.world.intervention_args['reflect'].update(record)
                        self.world.intervention_args['reflect']['time_minutes'] = int(self.world.intervention_args['reflect']['threat_activation_time']/60)
                change = True
        if AC.name == 'AC_CORNELL_TA2_TEAMTRUST':
            influence['coordination'] = influence.get('coordination', 0)-sum(gap.values())/100
            influence['team monitoring'] = influence.get('team monitoring', 0)-sum(gap.values())/100
            dysfunctional = [pair for pair in noncompliance if gap[pair] > 1]
            change = True
            if dysfunctional:
                # What if two? 
                self.world.intervention_args['report drop'] = {'Player': dysfunctional[0][1], 'Requestor': dysfunctional[0][0]}
                if self.team.leader is None or len(self.team.leader) > 1 or self.team.leader[0] in dysfunctional[0]:
                    self.world.intervention_args['report drop']['Leader'] = 'Team'
                else:
                    self.world.intervention_args['report drop']['Leader'] = self.team.leader[0]
                self.setState('valid report drop', True, recurse=True)
            else:
                self.setState('valid report drop', False, recurse=False)
            waiting = {}
            for pair, count in gap.items():
                waiting[pair[0]] = waiting.get(pair[0], 0) + count
            wait_count = max(waiting.values())
            if wait_count > 5:
                self.world.intervention_args['remind practices'] = {'Player': next(iter([p for p, count in waiting.items() if count == wait_count]))}
                self.setState('valid remind practices', True, recurse=True)
            else:
                self.setState('valid remind practices', False, recurse=False)
        if leadership:
            self.team.leader = [name for name, value in leadership.items() if value == max(leadership.values())]
            change = True
        beliefs = self.getBelief(model=self.get_true_model())
        record = {'timestamp': self.world.now, 
                  'trial': self.world.info['trial_number']}
        for process, value in influence.items():
            old_dist = self.world.getState(self.team.name, process, beliefs)
            expected = value > 0
            prob_unexpected = pow(self.base_probability['unexpected'], abs(value))
            new_dist = {expected: old_dist.get(expected)*(1-prob_unexpected) + old_dist.get(not expected)*(1-prob_unexpected-self.base_probability['null']),
                        not expected: old_dist.get(expected)*prob_unexpected + old_dist.get(not expected)*(prob_unexpected+self.base_probability['null'])}
            new_dist = Distribution(new_dist)
            new_dist.normalize()
            self.world.setState(self.team.name, process, new_dist, beliefs)
            record[process] = new_dist[True]
            change = True
        beliefs.select(True)
        self.belief_data = pandas.concat([self.belief_data, pandas.DataFrame([record])], ignore_index=True)
        # print(AC.name, influence)


def make_asi(world, team_agent, players, acs={}, config=None):
    agent = ASI(world, acs, config)
    world.addAgent(agent)
    agent.add_interventions(players, team_agent)
    for feature in team_agent.processes:
        agent.setReward(maximizeFeature(stateKey(team_agent.name, feature), agent.name), 1)
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
        self.leader = world.prior_leader

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
