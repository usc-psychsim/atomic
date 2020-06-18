# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from argparse import ArgumentParser
import logging

from psychsim.world import World, WORLD
from psychsim.pwl import stateKey, actionKey, modelKey, VectorDistribution
from new_locations_fewacts import Locations, Directions
from victims_fewacts import Victims
from SandRMap import getSandRMap, getSandRVictims, getSmallSandRMap, getSmallSandRVictims, checkSRMap
from helpers import runMMBelUpdate, setBeliefs, setBeliefsNoVics
from ftime import FatherTime

def createWorld(numVictims=0):
    # MDP or POMDP
    Victims.FULL_OBS = True

    ##################
    ##### Get Map Data
    SandRLocs = getSmallSandRMap()
    SandRVics = getSmallSandRVictims()
    if numVictims > 0:
        # Subset of possible victims
        SandRVics = {label: color for label,color in list(SandRVics.items())[:numVictims]}
    ##################

    world = World(stateType=VectorDistribution)

    triageAgent = world.addAgent('TriageAg1')
    agent = world.addAgent('ATOMIC')
    clock = FatherTime(world, False)


    VICTIMS_LOCS = list(SandRVics.keys())
    VICTIM_TYPES = [SandRVics[v] for v in VICTIMS_LOCS]
    Victims.world = world
    Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], list(SandRLocs.keys()))
    Victims.makePreTriageActions(triageAgent)
    Victims.makeTriageAction(triageAgent)

    ################# Locations and Move actions
    Locations.EXPLORE_BONUS = 0
    Locations.world = world
    Locations.makeMapDict(SandRLocs)
    Locations.makePlayerLocation(triageAgent, Victims, "E2")

    ## These must come before setting triager's beliefs
    world.setOrder([{triageAgent.name}])

    ## Set players horizons
    triageAgent.setAttribute('horizon',4)

    ####### Test if action effects are back
    #Locations.move(triageAgent, Directions.W)
    #clock.tick()
    #world.printState(beliefs=False)
    return world


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-v','--victims',type=int,default=0,help='Number of victims to include (default is all of them')
    parser.add_argument('-n','--number',type=int,default=-1,help='Number of unconstrained simulation steps to run (0 means run forever)')
    parser.add_argument('-f','--filename',help='Filename to save world to')
    parser.add_argument('-d','--debug',default='WARNING',help='Level of logging detail')

    opts = vars(parser.parse_args())
    # Extract logging level from command-line argument
    level = getattr(logging, opts['debug'].upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid debug level: %s' % opts['debug'])
    logging.basicConfig(level=level)

    world = createWorld(opts['victims'])
    if opts['filename']:
        world.save(opts['filename'])
    triageAgent = world.agents['TriageAg1']
    agent = world.agents['ATOMIC']
    triageAgent.omega = [key for key in world.state.keys()]
    triageAgent.resetBelief(stateType=VectorDistribution)

    if opts['number'] < 0:
        ###############  ACTIVATE *ONE* OF THE FOLLOWING BLOCKS TO SEE THE ASSOCIATED ISSUE ############### 

        ############### The following shows incorrect beleifs of the triager about his own last 
        ############### action and thus new location.
        #setBeliefsNoVics(world, agent, triageAgent)
        #Locations.move(triageAgent, Directions.W)
        #world.printBeliefs(triageAgent.name)


        ########## Empty world state!
        #setBeliefsNoVics(world, agent, triageAgent)
        #Locations.move(triageAgent, Directions.W)
        #world.printState(beliefs=False)

        ############### The following breaks the assertion len(agent.getBelief()) ==1 
        ############### action and thus new location.
        print(world.resymbolize())
        actions = [Locations.moveActions[triageAgent.name][Directions.W],
                   [Victims.STR_FOV_VAR, 'victim0'],
                   Locations.moveActions[triageAgent.name][Directions.E]]
        #           Victims.getPretriageAction(triageAgent.name, Victims.crosshairActs)]
        runMMBelUpdate(world, agent, triageAgent, actions, Locations)
        print(world.resymbolize())
    else:
        t = 1
        while opts['number'] == 0 or opts['number'] >= t:
            print('Step %d' % (t))
            world.step(select=True)
            t += 1
