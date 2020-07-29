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
from SandRMap import getSandRMap, getSandRVictims, checkSRMap
from helpers import runMMBelUpdate, setBeliefs, setBeliefsNoVics, anding
from ftime import FatherTime
from psychsim.helper_functions import get_true_model_name
from psychsim.probability import Distribution
from maker import makeWorld

PREFER_NONE_MODEL = 'prefer_none'
PREFER_GOLD_MODEL = 'prefer_gold'
PREFER_GREEN_MODEL = 'prefer_green'
MODEL_SELECTION = 'distribution'

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
    adj_fname = 'falcon_adjacency_v1.1_OCN'
    vics_fname = 'falcon_vic_locs_v1.1_OCN'
    start_room = 'el'
    isSmall = False

    SandRLocs = getSandRMap(small=isSmall,fname=adj_fname)
    SandRVics = getSandRVictims(small=isSmall,fname=vics_fname)
    print("making world")
    world, player, atomic, dbg = makeWorld('TriageAg1',start_room,SandRLocs,SandRVics)

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

    ##### Simulation
    cmd = 'blank'
    while cmd != '':
      legalActions = player.getLegalActions()
      player_state = player.getState('loc')
      print("Player state: ", player_state)
      #  print("reward: ",player.reward())
      print('Legal Actions:')
      for a,n in zip(legalActions,range(len(legalActions))):
          print(n,': ',a)

      cmd = input('select action, or type "s" to print belief, press return with no entry to stop: ')
      try:
          cmd_int = int(cmd)
          Victims.world.step(list(legalActions)[cmd_int],select=True)
      except:
          #do nothing
          pass

      print('Triage Agent Reward: ', player.reward())
      if cmd == 's':
          world.printBeliefs(atomic.name)
          #  world.printState()
      elif cmd == '':
          print('Finishing Simulation')
