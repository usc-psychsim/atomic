"""
An agent that observes people performing the Minecraft search & rescue task,
makes inferences about their current mental state, and intervenes when
to improve task performance
"""
import copy

from psychsim.probability import Distribution
from psychsim.pwl import modelKey, rewardKey, isStateKey, state2agent, state2feature
from psychsim.action import ActionSet

# Possible player model parameterizations
DEFAULT_MODELS = {'horizon': {'myopic': 2, 'strategic': 4},
                  'reward': {'preferyellow': {'Green': 1, 'Gold': 3}, 'nopreference': {'Green': 1, 'Gold': 1}},
                  'rationality': {'unskilled': 0.5, 'skilled': 1}}
DEFAULT_IGNORE = ['horizon', 'rationality']


def make_observer(world, team, name='ATOMIC'):
    """
    :param world: the PsychSim World
    :param team: names of agents to be modeled
    :type team: List[str]
    :param name: name of the agent to be created, defaults to 'ATOMIC'
    :type name: str
    :return: the newly created agent, also added to the given World
    :rtype: Agent
    """
    agent = world.addAgent(name, avoid_beliefs=False)
    return agent

def create_player_models(world, players, victims=None):
    param_names = None
    zero_models = {}
    null_actions = {}
    models = {}
    null_models = {}
    for player_name, param_list in players.items():
        # get the canonical name of the "true" player model
        player = world.agents[player_name]
        true_model = player.models[player.get_true_model()]
        new_models = []
        for param_dict in param_list:
            if param_names is None:
                param_names = sorted(param_dict.keys())
            param_str = '_'.join([f'{param}{param_dict[param]}' for param in param_names])
            model_name = f'{player_name}_{param_str}'
            tom_level = param_dict.get('tom', 0)
            null_zero = param_dict.get('null_zero', 0) == 0
            if null_zero and len(null_actions) == 0:
                for name in players:
                    # Find null action
                    for action in world.agents[name].actions:
                        if action['verb'] == 'noop':
                            null_actions[name] = action
                            break
                    else:
                        raise ValueError(f'Unable to find noop for {player_name}')
            if tom_level > 0:
                # Nonzero Theory of Mind
                new_model = player.n_level(tom_level, parent_models={player_name: {true_model['name']}}, null=null_actions, 
                    prefix=model_name, selection=param_dict.get('selection', 'distribution'))[true_model['name']]
            else:
                # Build a random 0-level model
                try:
                    new_model = zero_models[player_name]
                except KeyError:
                    my_models = world.agents[player_name].get_nth_level(0, parent=true_model['name'])
                    if len(my_models) == 0:
                        zero_models[player_name] = new_model = world.agents[player_name].zero_level()
                    elif len(my_models) > 1:
                        raise ValueError(f'Multiple zero-level models found for {player_name}')
                    else:
                        zero_models[player_name] = new_model = next(iter(my_models))
                new_model = player.models[new_model]
            for key, value in param_dict.items():
                if key == 'reward':
                    if value > 0:
                        R = copy.deepcopy(player.getReward()[true_model['name']])
                        vector = R.getLeaf()[rewardKey(player_name, True)]
                        for var in world.variables:
                            if isStateKey(var) and state2agent(var) == player_name and state2feature(var)[:8] == '(visited':
                                if value == 1:
                                    vector[var] = 1
                                elif value == 2:
                                    vector[var] = victims.get(state2feature(var)[10:-1], {}).get('regular', 0)+5*victims.get(state2feature(var)[10:-1], {}).get('critical', 0)
                        player.setAttribute('R', R, new_model['name'])
                elif key != 'selection':
                    new_model[key] = value
            new_model['parameters'] = param_dict
#            if new_model['parent'] != zero_model:
#                beliefs = player.create_belief_state(model=model_name)
            new_models.append(new_model)
        models[player_name] = new_models
    return models

def set_player_models(world, observer_name, players, victims=None):
    """
    :param world: the PsychSim World
    :type world: World
    :param observer_name: the name of the agent whose beliefs we will be specifying
    :type observer_name: str
    :param players: player names and a list of model parameters
    :type players: Dict[List] 
    :param victims: specification of victims
    :type victims: Victims
    """
    observer = world.agents[observer_name]

    # observer does not model itself
    observer.create_belief_state()
    models = create_player_models(world, players)
    for player_name, new_models in models.items():
        player = world.agents[player_name]
        # observer has uniform prior distribution over possible player models
        if len(player.models) > 1:
            world.setMentalModel(observer.name, player.name,
                                 Distribution({new_model['name']: 1. / len(new_models) for new_model in new_models}))

    # observer sees everything except true models
    observer.set_observations()
