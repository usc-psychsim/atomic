from psychsim.pwl.plane import equalRow
from psychsim.pwl.matrix import setToConstantMatrix
from psychsim.pwl.tree import makeTree
from psychsim.action import Action, ActionSet
from psychsim.reward import maximizeFeature

import operator

from atomic.analytic.ihmc_wrapper import JAGWrapper
from atomic.analytic.gallup_wrapper import GelpWrapper
from atomic.analytic.cornell_wrapper import ComplianceWrapper
from atomic.analytic.cmu_wrapper import TEDWrapper

# ['AC_Aptima_TA3_measures', 'AC_CMUFMS_TA2_Cognitive', 'AC_CORNELL_TA2_ASI-FACEWORK', 
# 'AC_CORNELL_TA2_TEAMTRUST', 'AC_IHMC_TA2_Dyad-Reporting', 'AC_IHMC_TA2_Location-Monitor', 
# 'AC_IHMC_TA2_Player-Proximity', 'AC_Rutgers_TA2_Utility', 'AC_UAZ_TA1_ToMCAT-SpeechAnalyzer', 
# 'PyGL_FoV_Agent', 'ac_cmu_ta2_beard', 'ac_cmu_ta2_ted', 'ac_gallup_ta2_gelp',
# 'ac_gallup_ta2_gold', 'ac_ihmc_ta2_joint-activity-interdependence', 'ac_ucf_ta2_playerprofiler', 
# 'asistdataingester', 'gui', 'metadata-web', 'pygl_fov', 'simulator', 'tomcat_speech_analyzer',
# 'uaz_dialog_agent']


class AC_model:
    def __init__(self, name, **kwargs):
        self.name = name
        self.filters = kwargs.get('filters', set())
        self.wrapper = kwargs.get('wrapper', None)
        if self.wrapper is not None:
            self.wrapper = self.wrapper[0](*self.wrapper[1])
        self.variables_team = kwargs.get('team', {})
        self.variables_player = kwargs.get('player', {})
        self.variables_pair = kwargs.get('pair', {})
        self.variables = {}

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

    def augment_world(self, world, team_agent, players):
        """
        :type team_agent: Agent
        :type players: dict(str->Agent)
        """
        # Player-specific variables
        for player in players:
            for var_name, table in self.variables_player.items():
                if isinstance(table['values'], list):
                    var = world.defineState(player, f'{self.name} {var_name}', list, lo=table['values'])
                    world.setFeature(var, table['values'][0])
                elif table['values'] is int:
                    var = world.defineState(player, f'{self.name} {var_name}', int, lo=0, hi=table.get('hi', 1))
                    world.setFeature(var, 0)
                else:
                    raise TypeError(f'Unable to create variable {self.name} '
                                    f'{var_name} of type {table["values"].__class__.__name__}')
                self.variables[var] = table
        # Pairwise variables
        for player in players:
            for other in players:
                if other != player:
                    for var_name, table in self.variables_pair.items():
                        if isinstance(table['values'], list):
                            var = world.defineRelation(player, other, f'{self.name} {var_name}', list, lo=table['values'])
                            world.setFeature(var, table['values'][0])
                        elif table['values'] is int:
                            var = world.defineRelation(player, other, f'{self.name} {var_name}', int, lo=0, hi=table.get('hi', 1))
                            world.setFeature(var, 0)
                        else:
                            raise TypeError(f'Unable to create variable {self.name} {var_name} of type {table["values"].__class__.__name__}')
                        self.variables[var] = table
        # Team-wide variables
        for var_name, table in self.variables_team.items():
            if isinstance(table['values'], list):
                var = world.defineState(team_agent.name, f'{self.name} {var_name}', list, lo=table['values'])
                world.setFeature(var, table['values'][0])
            elif table['values'] is int:
                var = world.defineState(team_agent.name, f'{self.name} {var_name}', int, lo=0, hi=table.get('hi', 1))
                world.setFeature(var, 0)
            else:
                raise TypeError(f'Unable to create variable {self.name} {var_name} of type {table["values"].__class__.__name__}')
            self.variables[var] = table


AC_specs = {'ac_cmu_ta2_ted': 
            {'filters': {'agent/ac/cmuta2-ted-ac/ted'},
             'wrapper': (TEDWrapper, ('cmu', 'ted')),
             'team': {'skill use': {'values': int, 'hi': 2,
                                    'ASI reward': 1},
                      'task strategy': {'values': int, 'hi': 2,
                                        'ASI reward': 1},
                      'collective effort': {'values': int, 'hi': 2,
                                            'ASI reward': 1},
                      'communication': {'values': int, 'hi': 2,
                                        'ASI reward': 1,
                                        'effects': {'report drop': {'object': operator.gt}}},
                      },
             'player': {'skill use': {'values': int, 'hi': 2,
                                      'condition': operator.gt},
                        'task strategy': {'values': int, 'hi': 2,
                                          'condition': operator.gt},
                        'collective effort': {'values': int, 'hi': 2,
                                              'condition': operator.gt,
                                              'effects': {'report drop': {'about': operator.gt}}},
                        'communication': {'values': int, 'hi': 2,
                                          'effects': {'report drop': {'object': operator.gt}}},
                        },
             'pair': {},
             },
            'ac_cmu_ta2_beard':
            {'player': {'anger': {'values': int, 'hi': 2,
                                  'effects': {'cheer': {'object': operator.lt}},
                                  'process': {'affect management': -1}},
                        'anxiety': {'values': int, 'hi': 2,
                                    'effects': {'cheer': {'object': operator.lt}},
                                    'process': {'affect management': -1}},
                        'minecraft skill': {'values': int, 'hi': 2,
                                            'condition': operator.gt},
                        'social perceptiveness': {'values': int, 'hi': 2}}},
            'AC_CORNELL_TA2_TEAMTRUST':
            {'filters': {'agent/ac/player_compliance'},
             'wrapper': (ComplianceWrapper, ('cornell', 'compliance')),
             'pair': {'open requests': {'values': int},
                      'compliance': {'values': int},
                      'compliance rate': {'values': int, 'hi': 1},
                      'response start': {'values': int, 'hi': 1},
                      'response action': {'values': int, 'hi': 1}}},
            'ac_gallup_ta2_gelp': 
            {'filters': {'agent/gelp'},
             'wrapper': (GelpWrapper, ('gallup', 'gelp')),
             'player': {'leadership': {'values': int, 'hi': 1},
                        }},
            'ac_ihmc_ta2_joint-activity-interdependence':
            {'filters': {'observations/events/player/jag', 
                         'observations/events/mission',
                         'observations/events/player/role_selected'},
             'wrapper': (JAGWrapper, ('ihmc', 'jag'))},
            'AC_Rutgers_TA2_Utility':
            {'player': {'indiv entropy': {'values': int, 'hi': 1},
                        'marker entropy': {'values': int, 'hi': 1}}},
            'ac_ucf_ta2_playerprofiler':
            {'player': {'taskwork potential': {'values': int, 'hi': 1,
                                               'condition': operator.gt},
                        'teamwork potential': {'values': int, 'hi': 1}}},
            }


def make_ac_handlers(config=None):
    return {name: AC_model(name, **AC_spec) for name, AC_spec in AC_specs.items() 
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
