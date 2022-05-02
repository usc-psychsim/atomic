interventions = {  # Inter-mission AAR prompt
                   # Associated state: Descriptors from situation to highlight (implies descriptors of current situation are being maintained)
                   'reflect': {'object': 'player',
                               'template': 'I\'ve noticed an instance when ${object} was waiting for longer than usual. Do you remember ${situation}? Could you comment on a) what you think happened, b) how you could identify this the next time, c) what to do when you identify this occuring?'},
                   # Cheerleading action
                   'cheer': {'object': 'player',
                             'template': 'Great job, ${object}!'},
                   # Report performance change
                   # Associated state: Individual performance level, team leader
                   'report drop': {'object': 'player',
                                   'template': 'Can you check on ${object}? They haven\'t been responding.'},
                   # Recommend phase-sensitive plan (early)
                   # Associated state: Game phase
                   'notify early phase': {'object': 'team',
                                          'template': 'Team, it looks like you\'re working well to clear this section, however the building is large and spreading out early on may be useful.'},
                   # Recommend phase-sensitive plan (late)
                   # Associated state: Game phase
                   'notify late phase': {'object': 'team',
                                         'template': 'Team, the mission is nearing its end, it\'s time to work together in a high-value region and focus on transport and triaging to get points!'},
                   # Prompt for coordination best practices
                   # Associated state: Unassigned requests/goals
                   'remind practices': {'object': 'player',
                                        'template': 'No one has fulfilled ${object}\'s request. Can anyone help?'},
                   # Spread workload
                   # Associated state: workload of individual players
                   'distribute workload': {'object': 'player',
                                           'template': 'Can someone help ${object} who is currently overloaded?'},
                 }
