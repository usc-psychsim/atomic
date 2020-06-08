#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 22 16:14:44 2020

@author: mostafh
"""

from psychsim.probability import Distribution
from psychsim.pwl.vector import KeyedVector,VectorDistribution

from psychsim.world import World, WORLD
from psychsim.pwl import modelKey


world = World()
agent = world.addAgent('ATOMIC')
X = world.defineState(WORLD,'x')
Y = world.defineState(WORLD,'y')


k1 = world.defineState(agent.name, 'k1', bool)
k2 = world.defineState(agent.name, 'k2', bool)
d1 = Distribution({True:.2, False:.8})
d2 = Distribution({True:.3, False:.7})

world.setFeature(k1,d1)
world.setFeature(k2,d2)

agent.addAction({'verb': 'observe'})
world.setOrder([{agent.name}])
world.setJoint(VectorDistribution({
	KeyedVector({X: 0, Y: 0}): 0.40,
	KeyedVector({X: 0, Y: 1}): 0.1,
	KeyedVector({X: 1, Y: 0}): 0.05,
	KeyedVector({X: 1, Y: 1}): 0.45
	}))



# Agent does not model itself
agent.resetBelief(ignore={modelKey(agent.name)})
# Agent observes everything. Probably unnecessary.
agent.omega = {key for key in world.state.keys()}

agent.setBelief(k1,d1)
agent.setBelief(k2,d2)

world.setFeature(X, 0)

print('Agents belief\n')
world.printBeliefs(agent.name)
print('World state\n')
world.printState()

world.step()

print('Agents belief\n')
world.printBeliefs(agent.name)
