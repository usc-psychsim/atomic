from psychsim.pwl.plane import equalRow
from psychsim.pwl.tree import makeTree
from psychsim.action import Action, ActionSet
from psychsim.reward import maximizeFeature

import operator


class AC_model:
    def __init__(self, name, **kwargs):
        self.name = name
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

    def get_ASI_reward(self):
        return {var: table['ASI reward'] for var, table in self.variables.items()
                if 'ASI reward' in table}        

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
                    var = world.defineState(player, f'{self.name} {var_name}', int, lo=0)
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
                            var = world.defineRelation(player, other, f'{self.name} {var_name}', int, lo=0)
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
                var = world.defineState(team_agent.name, f'{self.name} {var_name}', int, lo=0)
                world.setFeature(var, 0)
            else:
                raise TypeError(f'Unable to create variable {self.name} {var_name} of type {table["values"].__class__.__name__}')
            self.variables[var] = table


AC_specs = {'CMU_TED': 
            {'team': {'skill use': {'values': ['lo', 'mid', 'hi'],
                                    'ASI reward': 1},
                      'task strategy': {'values': ['lo', 'mid', 'hi'],
                                        'ASI reward': 1},
                      'collective effort': {'values': ['lo', 'mid', 'hi'],
                                            'ASI reward': 1},
                      'communication': {'values': ['lo', 'mid', 'hi'],
                                        'ASI reward': 1},
                      },
             'player': {'skill use': {'values': ['lo', 'mid', 'hi'],
                                      'condition': operator.gt},
                        'task strategy': {'values': ['lo', 'mid', 'hi'],
                                          'condition': operator.gt},
                        'collective effort': {'values': ['lo', 'mid', 'hi'],
                                              'condition': operator.gt},
                        'communication': {'values': ['lo', 'mid', 'hi']},
                        },
             'pair': {},
             },
            'CMU_BEARD':
            {'player': {'anger': {'values': ['lo', 'mid', 'hi'],
                                  'effects': {'cheer': {'object': operator.lt}}},
                        'anxiety': {'values': ['lo', 'mid', 'hi'],
                                    'effects': {'cheer': {'object': operator.lt}}},
                        'minecraft skill': {'values': ['lo', 'mid', 'hi'],
                                            'condition': operator.gt},
                        'social perceptiveness': {'values': ['lo', 'mid', 'hi']}}},
            'Gallup_GELP': 
            {'player': {'leadership': {'values': ['lo', 'hi']},
                        }},
            'Cornell_Team_Trust':
            {'pair': {'open requests': {'values': int},
                      'compliance': {'values': int},
                      'compliance rate': {'values': ['lo', 'hi']},
                      'response start': {'values': ['lo', 'hi']},
                      'response action': {'values': ['lo', 'hi']}}},
            'UCF':
            {'player': {'taskwork potential': {'values': ['lo', 'hi'],
                                               'condition': operator.gt},
                        'teamwork potential': {'values': ['lo', 'hi']}}}
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
    if not player.hasAction({'verb': 'work on', 'object': victim}):
        tree = makeTree({'if': equalRow(var, 'complete'), 
                        True: False, False: True})
        player.addAction({'verb': 'work on', 'object': victim}, tree)
    for child in jag['children']:
        add_joint_activity(world, player, team, child)


if __name__ == '__main__':
    ACs = make_ac_handlers()
    print(ACs)
