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

def create_player_models(world, players):
    models = {}
    param_names = None
    zero_models = {player_name: [model_name for model_name in world.agents[player_name].models if model_name[-4:] == 'zero'][0]
        for player_name in players}
    null_actions = {}
    for player_name in players:
        for action in world.agents[player_name].actions:
            if action['verb'] == 'noop':
                null_actions[player_name] = action
                break
        else:
            raise ValueError(f'Unable to find noop for {player_name}')
    null_models = {player_name: world.agents[player_name].zero_level(null=null_actions[player_name]) for player_name in players}
    for player_name, param_list in players.items():
        # get the canonical name of the "true" player model
        player = world.agents[player_name]
        zero_model = zero_models[player_name]
        true_model = player.models[player.get_true_model()]
        new_models = []
        for param_dict in param_list:
            if param_names is None:
                param_names = sorted(param_dict.keys())
            param_str = '_'.join([f'{param}{param_dict[param]}' for param in param_names])
            model_name = f'{player_name}_{param_str}'
            if param_dict.get('tom', 0) > 0:
                new_model = player.addModel(model_name, parent=true_model['name'], selection=param_dict.get('selection', 'distribution'), beliefs=True, static=True)
            elif param_dict.get('null_zero', 0) == 0:
                new_model = player.addModel(model_name, parent=zero_model, selection=param_dict.get('selection', 'distribution'), beliefs=True, static=True)
            else:
                # Don't bother building other versions of the zero-level models for zero-level agents
                continue 
            for key, value in param_dict.items():
                if key == 'tom':
                    if value == 1:
                        if param_dict.get('others', 1) == 1:
                            new_model['models'] = {other_name: null_models[other_name] for other_name in players if other_name != player_name}
                        else:
                            new_model['models'] = {other_name: zero_models[other_name] for other_name in players if other_name != player_name}
                    elif value > 1:
                        raise ValueError(f'Have not implemented {value}-level ToM yet')
                elif key == 'reward':
                    if value == 1:
                        R = copy.deepcopy(player.getReward()[true_model['name']])
                        vector = R.getLeaf()[rewardKey(player_name, True)]
                        for var in world.variables:
                            if isStateKey(var) and state2agent(var) == player_name and state2feature(var)[:8] == '(visited':
                                vector[var] = 1
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
