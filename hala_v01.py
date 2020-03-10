# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.agent import Agent
from psychsim.pwl import modelKey, rewardKey, Distribution, stateKey

from fires import Fires
from victims import Victims
from locations import Locations
from helpers import printAgent, setBeliefs

# create world and add human triageAgents
world = World()
fireAgent = Agent('FireAg1')
world.addAgent(fireAgent)
triageAgent = Agent('TriageAg1')
world.addAgent(triageAgent)
# ASIST Agent
agent = world.addAgent('ATOMIC')

################# Victims and triage actions
Victims.world = world
Victims.makeVictims([human.name for human in [fireAgent, triageAgent]])
Victims.makeTriageAction(triageAgent)
for human in [fireAgent, triageAgent]:
    Victims.makeVictimObs(human)


################# Locations and Move actions
Locations.world = world
Locations.makeMap(6, [(0,1), (1,2), (2,3), (3,4), (1,5)])
Locations.makePlayerLocation(fireAgent, 0)
Locations.makePlayerLocation(triageAgent, 1)


################# Fires and extinguish actions
Fires.world = world
Fires.firemen = [fireAgent]
Fires.allPlayers = [triageAgent, fireAgent]
Fires.makeFires([0])

################# ORDER           
#world.setOrder([{fireAgent.name}, {triageAgent.name}]) #, 
world.setOrder([{triageAgent.name}]) #, 

################# Set beliefs, observables and things to ignore
setBeliefs(world, agent, triageAgent, fireAgent)

################# 
printAgent(world, triageAgent.name)
world.printBeliefs(triageAgent.name)
#Locations.move(triageAgent, 5)
#printAgent(world, triageAgent.name)

##world.printBeliefs(agent.name)
###Locations.move(triageAgent, 3)
###world.printBeliefs(agent.name)
###
#

#showOptions()
#triageLoc = stateKey(triageAgent.name, 'loc')
#Locations.move(triageAgent, 5)
#triageBel = triageAgent.getBelief()[trueTriageModel]
#print(triageBel[triageLoc], world.state[triageLoc])
#
#showOptions()
#
