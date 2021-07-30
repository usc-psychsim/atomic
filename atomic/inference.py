"""
An agent that observes people performing the Minecraft search & rescue task,
makes inferences about their current mental state, and intervenes when
to improve task performance
"""
from psychsim.probability import Distribution
from psychsim.pwl import modelKey

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
    agent = world.addAgent(name)
    return agent


def set_player_models(world, observer_name, players, victims):
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

    for player_name, param_list in players.items():
        # get the canonical name of the "true" player model
        player = world.agents[player_name]
        true_model = player.get_true_model()

        for param_dict in param_list:
            model_name = param_dict['name']
            if model_name != true_model:
                player.addModel(model_name, parent=true_model,
                                horizon=param_dict.get('horizon', 2),
                                rationality=param_dict.get('rationality', 0.5),
                                selection=param_dict.get('selection', 'distribution'))
            if isinstance(next(iter(param_dict['reward'].keys())), str):
                victims.makeVictimReward(player, model_name, param_dict['reward'])
            else:
                for feature, weight in param_dict['reward'].items():
                    feature.set_reward(player, weight, model_name)
            beliefs = player.resetBelief(model=model_name, ignore={modelKey(observer.name)})

        # observer has uniform prior distribution over possible player models
        if len(player.models) > 1:
            world.setMentalModel(observer.name, player.name,
                                 Distribution({param_dict['name']: 1. / (len(player.models) - 1) for param_dict in param_list}))

    # observer sees everything except true models
    observer.set_observations()
