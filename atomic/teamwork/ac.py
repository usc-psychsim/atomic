from psychsim.pwl.keys import stateKey, binaryKey
from psychsim.pwl.plane import equalRow
from psychsim.pwl.matrix import setToConstantMatrix
from psychsim.pwl.tree import makeTree
from psychsim.action import Action, ActionSet
from psychsim.reward import maximizeFeature

import json
import operator

from atomic.analytic.acwrapper import ACWrapper
from atomic.analytic.cmu_wrapper import TEDWrapper, BEARDWrapper
from atomic.analytic.cornell_wrapper import ComplianceWrapper
from atomic.analytic.gallup_wrapper import GelpWrapper, GOLDWrapper
from atomic.analytic.ihmc_wrapper import JAGWrapper
from atomic.analytic.rutgers_wrapper import BeliefDiffWrapper
from atomic.analytic.ucf_wrapper import PlayerProfileWrapper

# ['AC_Aptima_TA3_measures', 'AC_CMUFMS_TA2_Cognitive', 'AC_CORNELL_TA2_ASI-FACEWORK', 
# 'AC_CORNELL_TA2_TEAMTRUST', 'AC_IHMC_TA2_Dyad-Reporting', 'AC_IHMC_TA2_Location-Monitor', 
# 'AC_IHMC_TA2_Player-Proximity', 'AC_Rutgers_TA2_Utility', 'AC_UAZ_TA1_ToMCAT-SpeechAnalyzer', 
# 'PyGL_FoV_Agent', 'ac_cmu_ta2_beard', 'ac_cmu_ta2_ted', 'ac_gallup_ta2_gelp',
# 'ac_gallup_ta2_gold', 'ac_ihmc_ta2_joint-activity-interdependence', 'ac_ucf_ta2_playerprofiler', 
# 'asistdataingester', 'gui', 'metadata-web', 'pygl_fov', 'simulator', 'tomcat_speech_analyzer',
# 'uaz_dialog_agent']


class AC_model:
    def __init__(self, name, participant_map, **kwargs):
        self.name = name
        self.participant_map = participant_map
        self.filters = kwargs.get('filters', set())
        self.wrapper = kwargs.get('wrapper', None)
        if self.wrapper is not None:
            self.wrapper = self.wrapper[0](*self.wrapper[1])
        self.variables = kwargs.get('variables', {})
        self.all_topics = set()
        self.debugged = False

    def process_msg(self, msg, mission_time=None):
        msg_topic = msg.get('topic', '')
        state_delta = {}
        if self.wrapper:
            data = self.wrapper.handle_message(msg_topic, msg['msg'], msg['data'], mission_time)
        else:
            data = []
        self.all_topics.add(msg_topic)
        # add_joint_activity(world, world.agents[data['participant_id']], team.name, data['jag'])
        return state_delta

    def get_effects(self, intervention):
        """
        :return: any effects on this AC's variables by the given intervention
        """
        if isinstance(intervention, Action) or isinstance(intervention, ActionSet):
            intervention = intervention['verb']
        return {var: table['effects'][intervention] for var, table in self.variables.items() 
                if 'effects' in table and intervention in table['effects']}

    def get_field(self, field):
        return {var: table[field] for var, table in self.variables.items()
                if field in table}    

    def get_ASI_reward(self):
        return self.get_field('ASI reward')

    def get_conditions(self):
        return self.get_field('condition')

    def get_player_variable(self, player, var_name):
        return stateKey(player, f'{self.name} {var_name}')

    def get_pair_variable(self, player1, player2, var_name):
        return binaryKey(player1, player2, f'{self.name} {var_name}')

    def get_team_variable(self, team_name, var_name):
        return stateKey(team_name, f'{self.name} {var_name}')

    def define_variable(self, world, key, table):
        if isinstance(table['values'], list):
            world.defineVariable(key, list, lo=table['values'])
            world.setFeature(key, table['values'][0])
        elif table['values'] is int:
            world.defineVariable(key, int, lo=0, hi=table.get('hi', 1))
            world.setFeature(key, 0)
        else:
            raise TypeError(f'Unable to create variable {key} of type {table["values"].__class__.__name__}')

    def augment_world(self, world, team_agent, players):
        """
        :type team_agent: Agent
        :type players: dict(str->Agent)
        """
        for var_name, table in self.variables.items():
            if 'object' not in table:
                self.logger.warning(f'No player/pair/team specification for variable {var_name} in AC {self.name}')
            elif table['object'] == 'player':
                # Player-specific variables
                for player in players:
                    key = self.get_player_variable(player, var_name)
                    self.define_variable(world, key, table)
            elif table['object'] == 'pair':
                # Pairwise variables
                for player in players:
                    for other in players:
                        if other != player:
                            key = self.get_pair_variable(player, other, var_name)
                            world.relations[var_name] = world.relations.get(var_name, {}) | {key: {'subject': player, 'object': other}}
                            self.define_variable(world, key, table)
            elif table['object'] == 'team':
                # Team-wide variables
                key = self.get_team_variable(team_agent.name, var_name)
                self.define_variable(world, key, table)


AC_specs = {'AC_CMUFMS_TA2_Cognitive':
            {'filters': {'agent/measure/AC_CMUFMS_TA2_Cognitive/load'}},
            'ac_cmu_ta2_ted': 
            {'filters': {'agent/ac/ac_cmu_ta2_ted/ted'},
             'wrapper': (TEDWrapper, ('cmu', 'ted')),
             'variables': {'skill use': {'values': int, 'hi': 2, 'object': 'team',
                                         'ASI reward': 1},
                           'task strategy': {'values': int, 'hi': 2, 'object': 'team',
                                             'ASI reward': 1},
                           'collective effort': {'values': int, 'hi': 2, 'object': 'team',
                                                 'ASI reward': 1},
                           'communication': {'values': int, 'hi': 2, 'object': 'team',
                                             'ASI reward': 1,
                                             'effects': {'report drop': {'object': operator.gt}}}},
             },
            'ac_cmu_ta2_beard':
            {'filters': {'agent/ac/ac_cmu_ta2_beard/beard'},
             'wrapper': (BEARDWrapper, ('cmu', 'beard')),
             'variables': {'anger': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 1, 'object': 'player',
                                     'effects': {'cheer': {'object': operator.lt}},
                                     'process': {'affect management': -1}},
                           'anxiety': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 1, 'object': 'player',
                                       'effects': {'cheer': {'object': operator.lt}},
                                       'process': {'affect management': -1}},
                           'rmie': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 0.5, 'object': 'player',
                                    'effects': {'cheer': {'object': operator.lt}},
                                    'process': {'affect management': -1}},
                           'walking_skill': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 0.5, 'object': 'player',
                                             'condition': operator.gt},}},
            'AC_CORNELL_TA2_ASI-FACEWORK':
            {'wrapper': (ACWrapper, ('cornell', 'facework')),
            },
            'AC_CORNELL_TA2_TEAMTRUST':
            {'filters': {'agent/ac/goal_alignment', 'agent/ac/player_compliance'},
             'wrapper': (ComplianceWrapper, ('cornell', 'compliance')),
             'variables': {'open requests': {'values': int, 'object': 'pair'},
                           'compliance': {'values': int, 'object': 'pair'},
                           'compliance rate': {'values': int, 'hi': 1, 'object': 'pair'},
                           'response start': {'values': int, 'hi': 1, 'object': 'pair'},
                           'response action': {'values': int, 'hi': 1, 'object': 'pair'}}},
            'ac_gallup_ta2_gelp': 
            {'filters': {'agent/gelp'},
             'wrapper': (GelpWrapper, ('gallup', 'gelp')),
             'variables': {'leadership': {'values': int, 'hi': 1, 'object': 'player'}}},
            'ac_gallup_ta2_gold':
            {'filters': {'agent/gold'},
             'wrapper': (GOLDWrapper, ('cmu', 'beard')),
            },
            'AC_IHMC_TA2_Dyad-Reporting':
            {'filters': {'observations/events/player/dyad'}},
            'AC_IHMC_TA2_Location-Monitor':
            {'filters': {'observations/events/player/location'}},
            'AC_IHMC_TA2_Player-Proximity':
            {'filters': {'observations/events/player/proximity'}},
            'ac_ihmc_ta2_joint-activity-interdependence':
            {'filters': {'observations/events/player/jag', 
                         'observations/events/mission',
                         'observations/events/player/role_selected'},
             'wrapper': (JAGWrapper, ('ihmc', 'jag'))},
            'AC_Rutgers_TA2_Utility':
            {'filters': {'agent/ac/belief_diff'},
             'wrapper': (BeliefDiffWrapper, ('rutgers', 'belief_diff')),
             'variables': {'indiv entropy': {'values': int, 'hi': 1, 'object': 'player'},
                           'marker entropy': {'values': int, 'hi': 1, 'object': 'player'}}},
            'ac_ucf_ta2_playerprofiler':
            {'filters': {'agent/ac_ucf_ta2_playerprofiler/playerprofile'},
             'wrapper': (PlayerProfileWrapper, ('ucf', 'playerprofiler')),
             'variables': {'team-potential-category': {'values': int, 'hi': 1, 'object': 'player', 'mapping': {'HighTeam': 1, 'LowTeam': 0},},
                           'task-potential-category': {'values': int, 'hi': 1, 'object': 'player', 'mapping': {'HighTask': 1, 'LowTask': 0}}}},
            }


def make_ac_handlers(participant_map, config=None):
    return {name: AC_model(name, participant_map, **AC_spec) for name, AC_spec in AC_specs.items() 
            if config is None or config.getboolean('teamwork', f'ac_{name}', 
                                                   fallback=False)}


def add_joint_activity(world, player, team, jag):
    urn = jag['urn'].split(':')
    victim = jag['inputs']['victim-id']
    feature = f'{urn[-1]}_{victim}'
    # Create status variable for this joint activity
    var = world.defineState(player, feature, list, 
                            ['discovered', 'aware', 'preparing', 'addressing', 
                             'complete'])
    world.setFeature(var, 'discovered')
    # Add reward component for progressing through this activity
    for model in world.get_current_models()[player.name]:
        goal = maximizeFeature(var, player.name)
        player.setReward(goal, 1, model)
    # Add action for addressing this activity
    action_dict = {'verb': 'advance', 'object': victim}
    if not player.hasAction(action_dict):
        tree = makeTree({'if': equalRow(var, 'complete'), 
                        True: False, False: True})
        player.addAction(action_dict, tree)
        tree = makeTree({'if': equalRow(var, ['discovered', 'aware', 'preparing', 'addressing']),
                         'discovered': setToConstantMatrix(var, 'aware'),
                         'aware': setToConstantMatrix(var, 'preparing'),
                         'preparing': setToConstantMatrix(var, 'addressing'),
                         'addressing': setToConstantMatrix(var, 'complete'),
                         })
    for child in jag['children']:
        add_joint_activity(world, player, team, child)


if __name__ == '__main__':
    ACs = make_ac_handlers()
    print(ACs)
