from psychsim.pwl.keys import stateKey, WORLD
from psychsim.pwl.plane import thresholdRow

interventions = {  # Inter-mission AAR prompt
                   # Associated state: Descriptors from situation to highlight (implies descriptors of current situation are being maintained)
                   'reflect': {'object': 'team',
                               'template': ['Good luck, team!',
                                            'Back at the ${time_minutes}-minute mark, ${Player} had to wait ${wait_time} seconds while frozen in ${threat_room}. Could you comment on a) what you think happened, b) how you could identify this the next time, and c) what to do when you identify this occuring?'],
                               'effects': {'coordination': 1},
                               # Legal only before time 0
                               'legal': {'if': thresholdRow(stateKey(WORLD, 'clock'), 0), True: False, False: True},
                               'valid on start': True},
                   # Cheerleading action
                   'cheer': {'object': 'team',
                             'template': 'Great job getting that victim into the triage area, ${Player}!',
                             'effects': {'motivating': 1, 'affect management': 1, 'cognitive load': 1}},
                   # Report performance change
                   # Associated state: Individual performance level, team leader
                   'report drop': {'object': 'team',
                                   'template': '${Leader}, can you check on ${Player}? They haven\'t been responding to requests by ${Requestor}.',
                                   'effects': {'team monitoring': 1, 'cognitive load': 1}},
                   # Recommend phase-sensitive plan (early)
                   # Associated state: Game phase
                   'notify early phase': {'object': 'team',
                                          'template': ['Team, it looks like you\'re working well to clear this section; however, the building is large, so spreading out may be more useful now.',
                                                       'Team, remember to focus on exploring now.'],
                                          'effects': {'systems monitoring': 1, 'cognitive load': 1},
                                          'legal': {'if': thresholdRow(stateKey(WORLD, 'clock'), [300, 360]),
                                                    0: False, 1: True, 2: False},
                                          'valid on start': True
                                          },
                   # Recommend phase-sensitive plan (late)
                   # Associated state: Game phase
                   'notify late phase': {'object': 'team',
                                         'template': ['Team, the mission is nearing its end, it\'s time to work together in a more promising region and worry less about exploration!',
                                                      'Team, time to worry less about exploring!'],
                                         'effects': {'systems monitoring': 1, 'cognitive load': 1},
                                         'legal': {'if': thresholdRow(stateKey(WORLD, 'clock'), [600, 660]),
                                                   0: False, 1: True, 2: False},
                                         'valid on start': True
                                         },
                   # Prompt for coordination best practices
                   # Associated state: Unassigned requests/goals
                   'remind practices': {'object': 'team',
                                        'template': 'No one has fulfilled ${Player}\'s requests. Can anyone help?',
                                        'effects': {'coordination': 1, 'cognitive load': 1}},
                   # Spread workload
                   # Associated state: workload of individual players
                   'prompt activity': {'object': 'team',
                                       'template': 'There\'s not much activity. Is anyone stuck?',
                                       'effects': {'team monitoring': 1, 'coordination': 1, 'cognitive load': 1}},
                 }

intervention_patches = [[]]