from psychsim.pwl.keys import stateKey
from psychsim.reward import maximizeFeature


class AC_model:
    def __init__(self, name, **kwargs):
        self.name = name
        self.variables_team = kwargs.get('team', {})
        self.variables_player = kwargs.get('player', {})
        self.variables_pair = kwargs.get('pair', {})

    def augment_world(self, world, team_agent, players):
        """
        :type team_agent: Agent
        :type players: dict(str->Agent)
        """
        # Player-specific variables
        for player in players:
            for var_name, values in self.variables_player.items():
                if isinstance(values, list):
                    var = world.defineState(player, f'{self.name} {var_name}', list, lo=values)
                    world.setFeature(var, values[0])
                elif values is int:
                    var = world.defineState(player, f'{self.name} {var_name}', int, lo=0)
                    world.setFeature(var, 0)
                else:
                    raise TypeError(f'Unable to create variable {self.name} {var_name} of type {values.__class__.__name__}')
        # Pairwise variables
        for player in players:
            for other in players:
                if other != player:
                    for var_name, values in self.variables_pair.items():
                        if isinstance(values, list):
                            var = world.defineRelation(player, other, f'{self.name} {var_name}', list, lo=values)
                            world.setFeature(var, values[0])
                        elif values is int:
                            var = world.defineRelation(player, other, f'{self.name} {var_name}', int, lo=0)
                            world.setFeature(var, 0)
                        else:
                            raise TypeError(f'Unable to create variable {self.name} {var_name} of type {values.__class__.__name__}')
        # Team-wide variables
        for var_name, values in self.variables_team.items():
            if isinstance(values, list):
                var = world.defineState(team_agent.name, f'{self.name} {var_name}', list, lo=values)
                world.setFeature(var, values[0])
            elif values is int:
                var = world.defineState(team_agent.name, f'{self.name} {var_name}', int, lo=0)
                world.setFeature(var, 0)
            else:
                raise TypeError(f'Unable to create variable {self.name} {var_name} of type {values.__class__.__name__}')


AC_specs = {'CMU_TED': 
            {'team': {'skill use': ['lo', 'mid', 'hi'],
                      'task strategy': ['lo', 'mid', 'hi'],
                      'collective effort': ['lo', 'mid', 'hi'],
                      'communication': ['lo', 'mid', 'hi'],
                      },
             'player': {'skill use': ['lo', 'mid', 'hi'],
                        'task strategy': ['lo', 'mid', 'hi'],
                        'collective effort': ['lo', 'mid', 'hi'],
                        'communication': ['lo', 'mid', 'hi'],
                        },
             'pair': {},
             },
            'CMU_BEARD':
            {'player': {'anger': ['lo', 'mid', 'hi'],
                        'anxiety': ['lo', 'mid', 'hi'],
                        'minecraft skill': ['lo', 'mid', 'hi'],
                        'social perceptiveness': ['lo', 'mid', 'hi']}},
            'Gallup_GELP': 
            {'player': {'ideas': ['lo', 'hi'],
                        'focus': ['lo', 'hi'],
                        'coordinate': ['lo', 'hi'],
                        'monitor': ['lo', 'hi'],
                        'share': ['lo', 'hi'],
                        'plan': ['lo', 'hi'],
                        'agree': ['lo', 'hi'],
                        'help': ['lo', 'hi']}},
            'Cornell_Team_Trust':
            {'pair': {'open requests': int,
                      'compliance': int,
                      'compliance rate': ['lo', 'hi'],
                      'response start': ['lo', 'hi'],
                      'response action': ['lo', 'hi']}},
            'UCF':
            {'player': {'taskwork potential': ['lo', 'hi'],
                        'teamwork potential': ['lo', 'hi']}}
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
    for child in jag['children']:
        add_joint_activity(world, player, team, child)


if __name__ == '__main__':
    ACs = make_ac_handlers()
    print(ACs)
