# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: brett
"""
from argparse import ArgumentParser

from psychsim.world import World, WORLD
from psychsim.pwl import stateKey, actionKey, modelKey, rewardKey, equalRow, \
    noChangeMatrix, incrementMatrix, makeTree, setToConstantMatrix
from new_locations_fewacts import Locations, Directions
from victims_clr import Victims
from SandRMap import getSandRMap, getSandRVictims, getSmallSandRMap, getSmallSandRVictims, checkSRMap
from helpers import runMMBelUpdate, setBeliefs, setBeliefsNoVics, anding
from ftime import FatherTime
from psychsim.helper_functions import get_true_model_name
from psychsim.probability import Distribution

PREFER_NONE_MODEL = 'prefer_none'
PREFER_GOLD_MODEL = 'prefer_gold'
PREFER_GREEN_MODEL = 'prefer_green'
MODEL_SELECTION = 'distribution'


def createWorld(numVictims=0):
    # MDP or POMDP
    Victims.FULL_OBS = True

    ##################
    ##### Get Map Data
    SandRLocs = getSandRMap()
    SandRVics = getSandRVictims()
    if numVictims > 0:
        # Subset of possible victims
        SandRVics = {label: color for label,color in list(SandRVics.items())[:numVictims]}
    ##################

    world = World()

    player = world.addAgent('TriageAg1')
    agent = world.addAgent('ATOMIC')
    clock = FatherTime(world, False)


    VICTIMS_LOCS = list(SandRVics.keys())
    VICTIM_TYPES = [SandRVics[v] for v in VICTIMS_LOCS]
    Victims.world = world
    Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [player.name], list(SandRLocs.keys()))
    Victims.makePreTriageActions(player)
    Victims.makeTriageAction(player)

    ################# Locations and Move actions
    Locations.EXPLORE_BONUS = 0
    Locations.world = world
    Locations.makeMapDict(SandRLocs)
    Locations.makePlayerLocation(player, Victims, "CH4")

    ## These must come before setting triager's beliefs
    world.setOrder([{player.name}])

    ## Set players horizons
    player.setAttribute('horizon',4)

    ####### Test if action effects are back
    #Locations.move(player, Directions.W)
    #clock.tick()
    #world.printState(beliefs=False)
    return world

def createRwd(player,mm_list):
    for mm in mm_list:
        rwd_dict = mm_list[mm]
        rKey = rewardKey(player.name)
        crossKey = stateKey(player.name, Victims.STR_CROSSHAIR_VAR)
        testAllVics = {'if': equalRow(crossKey, ['none'] + Victims.vicNames),
                       0: noChangeMatrix(rKey)}
        for i, vobj in enumerate(Victims.victimAgents):
            vn = vobj.vicAgent.name
            rwd = rwd_dict[vobj.color]
            testAllVics[i+1] = anding([equalRow(stateKey(vn,'color'),'White'),
                                       equalRow(stateKey(vn, 'savior'), player.name),
                                       equalRow(actionKey(player.name), Victims.triageActs[player.name])],
                                setToConstantMatrix(rKey, rwd),
                                noChangeMatrix(rKey))

        player.setReward(makeTree(testAllVics),1.,mm)

if __name__ == '__main__':

    world = createWorld()
    player = world.agents['TriageAg1']
    atomic = world.agents['ATOMIC']

    # setup mental models and beliefs
    # atomic does not model itself
    atomic.resetBelief(ignore={modelKey(atomic.name)})

    # player does not model itself and sees everything except true models and its reward
    player.resetBelief(ignore={modelKey(atomic.name)})
    player.omega = {key for key in world.state.keys()
                   if key not in {modelKey(player.name), rewardKey(player.name), modelKey(atomic.name)}}

    # get the canonical name of the "true" player model
    true_model = get_true_model_name(player)

    # player's models
    HIGH_VAL = 100
    LOW_VAL = 10
    MEAN_VAL = (HIGH_VAL+LOW_VAL)/2

    mm_list = {PREFER_NONE_MODEL:{'Green':MEAN_VAL,'Gold':MEAN_VAL},
            #  PREFER_GREEN_MODEL:{'Green':HIGH_VAL,'Gold':LOW_VAL},
            PREFER_GOLD_MODEL:{'Green':LOW_VAL,'Gold':HIGH_VAL}}

    player.addModel(PREFER_NONE_MODEL, parent=true_model, rationality=.5, selection=MODEL_SELECTION)
    #  player.addModel(PREFER_GREEN_MODEL, parent=true_model, rationality=.5, selection=MODEL_SELECTION)
    player.addModel(PREFER_GOLD_MODEL, parent=true_model, rationality=.5, selection=MODEL_SELECTION)

    createRwd(player,mm_list)

    model_names = [name for name in player.models.keys() if name != true_model]

    # atomic has uniform prior distribution over possible player models
    world.setMentalModel(atomic.name, player.name,
                         Distribution({name: 1. / (len(player.models) - 1)
                                       for name in player.models.keys() if name != true_model}))

    # atomic sees everything except true models
    atomic.omega = {key for key in world.state.keys()
                      if key not in {modelKey(player.name), modelKey(atomic.name)}}

    world.printBeliefs(atomic.name)

    ##### Simulation
    cmd = 'blank'
#
    while cmd != '':
      legalActions = player.getActions()
      agent_state = player.getState('loc')
      print("Player state: ", agent_state)
      print("reward: ",player.reward())
      print('Legal Actions:')
      for a,n in zip(legalActions,range(len(legalActions))):
          print(n,': ',a)

      print()
      cmd = input('select action, or type "s" to print belief, press return with no entry to stop: ')
      try:
          cmd_int = int(cmd)
          Victims.world.step(list(legalActions)[cmd_int])
      except:
          #do nothing
          pass

      if cmd == 's':
          world.printBeliefs(atomic.name)
          print('Triage Agent Reward: ', player.reward())
      elif cmd == '':
          print('Finishing Simulation')
