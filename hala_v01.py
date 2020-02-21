# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.agent import Agent

from fires import Fires
from victims import Victims
from locations import Locations

# create world and add human players
world = World()
fireAgent = Agent('FireAg1')
world.addAgent(fireAgent)
triageAgent = Agent('TriageAg1')
world.addAgent(triageAgent)


################# Locations and Move actions
Locations.world = world
Locations.makeMap()
Locations.makePlayerLocation(fireAgent, 0)
Locations.makePlayerLocation(triageAgent, 2)

Locations.makeMoveActions(fireAgent)
Locations.makeMoveActions(triageAgent)

################# Victims and triage actions
Victims.world = world
Victims.makeVictims([human.name for human in [fireAgent, triageAgent]])
Victims.makeTriageAction(triageAgent)
Victims.makeVictimReward(triageAgent)

################# Fires and extinguish actions
Fires.world = world
Fires.makeFires()
Fires.makeExtinguishActions(fireAgent)
Fires.makeFirePenalty(fireAgent)

################# Do stuff !!
           
world.setOrder([{triageAgent.name}]) #, ,{fireAgent.name}

world.printState()

Locations.move(triageAgent, 1)

world.printState()

Locations.move(triageAgent, 2)

world.printState()

Victims.triage(triageAgent, 0)
    
world.printState()
