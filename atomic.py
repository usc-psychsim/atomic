"""
An agent that observes people performing the Minecraft search & rescue task, 
makes inferences about their current mental state, and intervenes when 
to improve task performance
"""
from psychsim.probability import Distribution
from psychsim.pwl import modelKey

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

def set_player_models(world, observer_name, player_name, victims, param_list):
    """
    :param world: the PsychSim World
    :type world: World
    :param observer_name: the name of the agent whose beliefs we will be specifying
    :type observer_name: str
    :param player_name: the name of the player agent to be modeled
    :type player_name: str
    :param param_list: list of dictionaries of model parameter specifications
    :type param_list: List[Dict]
    :param victims: specification of victims
    :type victims: Victims
    """
    observer = world.agents[observer_name]
    player = world.agents[player_name]

    # observer does not model itself
    observer.resetBelief(ignore={modelKey(observer.name)})

    # get the canonical name of the "true" player model
    true_model = player.get_true_model()

    for param_dict in param_list:
        model_name = param_dict['name']
        if model_name != true_model:
            player.addModel(model_name, parent=true_model, 
                horizon=param_dict.get('horizon',2),
                rationality=param_dict.get('rationality',0.5), 
                selection=param_dict.get('selection','distribution'))
        victims.makeVictimReward(player, model_name, param_dict['reward'])
        player.resetBelief(model=model_name, ignore={modelKey(observer.name)})

    # observer has uniform prior distribution over possible player models
    world.setMentalModel(observer.name, player.name,
                         Distribution({param_dict['name']: 1. / (len(player.models) - 1) for param_dict in param_list}))

    # observer sees everything except true models
    observer.omega = [key for key in world.state.keys()
                      if key not in {modelKey(player.name), modelKey(observer.name)}]  # rewardKey(player.name),
