import operator

from .acwrapper import ACWrapper
from .cmu_wrapper import TEDWrapper, BEARDWrapper
from .cornell_wrapper import ComplianceWrapper
from .gallup_wrapper import GelpWrapper, GOLDWrapper
from .ihmc_wrapper import JAGWrapper
from .rutgers_wrapper import BeliefDiffWrapper
from .ucf_wrapper import PlayerProfileWrapper


AC_specs = {'AC_CMUFMS_TA2_Cognitive':
            {'filters': {'agent/measure/AC_CMUFMS_TA2_Cognitive/load'}},
            'ac_cmu_ta2_ted': 
            {'filters': {'agent/ac/ac_cmu_ta2_ted/ted'},
             'wrapper': (TEDWrapper, ('cmu', 'ted')),
             'variables': {'skill use': {'values': int, 'hi': 2, 'object': 'team',
                                         'ASI reward': 1},
                           'task strategy': {'values': int, 'hi': 2, 'object': 'team',
                                             'ASI reward': 1},
                           'collective effort': {'values': int, 'hi': 2, 'object': 'team',
                                                 'ASI reward': 1},
                           'communication': {'values': int, 'hi': 2, 'object': 'team',
                                             'ASI reward': 1,
                                             'effects': {'report drop': {'object': operator.gt}}}},
             },
            'ac_cmu_ta2_beard':
            {'filters': {'agent/ac/ac_cmu_ta2_beard/beard'},
             'wrapper': (BEARDWrapper, ('cmu', 'beard')),
             'variables': {'anger': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 1, 'object': 'player',
                                     'effects': {'cheer': {'object': operator.lt}},
                                     'process': {'affect management': -1}},
                           'anxiety': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 1, 'object': 'player',
                                       'effects': {'cheer': {'object': operator.lt}},
                                       'process': {'affect management': -1}},
                           'rmie': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 0.5, 'object': 'player',
                                    'effects': {'cheer': {'object': operator.lt}},
                                    'process': {'affect management': -1}},
                           'walking_skill': {'values': int, 'hi': 1, 'prefix': '__player__', 'threshold': 0.5, 'object': 'player',
                                             'condition': operator.gt},}},
            'AC_CORNELL_TA2_ASI-FACEWORK':
            {'wrapper': (ACWrapper, ('cornell', 'facework')),
            },
            'AC_CORNELL_TA2_TEAMTRUST':
            {'filters': {'agent/ac/goal_alignment', 'agent/ac/player_compliance'},
             'wrapper': (ComplianceWrapper, ('cornell', 'compliance')),
             'variables': {'open requests': {'values': int, 'object': 'pair'},
                           'compliance': {'values': int, 'object': 'pair'},
                           'compliance rate': {'values': int, 'hi': 1, 'object': 'pair'},
                           'response start': {'values': int, 'hi': 1, 'object': 'pair'},
                           'response action': {'values': int, 'hi': 1, 'object': 'pair'}}},
            'ac_gallup_ta2_gelp': 
            {'filters': {'agent/gelp'},
             'wrapper': (GelpWrapper, ('gallup', 'gelp')),
             'variables': {'leadership': {'values': int, 'hi': 1, 'object': 'player'}}},
            'ac_gallup_ta2_gold':
            {'filters': {'agent/gold'},
             'wrapper': (GOLDWrapper, ('cmu', 'beard')),
            },
            'AC_IHMC_TA2_Dyad-Reporting':
            {'filters': {'observations/events/player/dyad'}},
            'AC_IHMC_TA2_Location-Monitor':
            {'filters': {'observations/events/player/location'}},
            'AC_IHMC_TA2_Player-Proximity':
            {'filters': {'observations/events/player/proximity'}},
            'ac_ihmc_ta2_joint-activity-interdependence':
            {'filters': {'observations/events/player/jag', 
                         'observations/events/mission',
                         'observations/events/player/role_selected'},
             'wrapper': (JAGWrapper, ('ihmc', 'jag'))},
            'AC_Rutgers_TA2_Utility':
            {'filters': {'agent/ac/belief_diff'},
             'wrapper': (BeliefDiffWrapper, ('rutgers', 'belief_diff')),
             'variables': {'indiv entropy': {'values': int, 'hi': 1, 'object': 'player'},
                           'marker entropy': {'values': int, 'hi': 1, 'object': 'player'}}},
            'ac_ucf_ta2_playerprofiler':
            {'filters': {'agent/ac_ucf_ta2_playerprofiler/playerprofile'},
             'wrapper': (PlayerProfileWrapper, ('ucf', 'playerprofiler')),
             'variables': {'team-potential-category': {'values': int, 'hi': 1, 'object': 'player', 'mapping': {'HighTeam': 1, 'LowTeam': 0},},
                           'task-potential-category': {'values': int, 'hi': 1, 'object': 'player', 'mapping': {'HighTask': 1, 'LowTask': 0}}}},
            }


def make_ac_handlers(config=None):
    return {name: ACWrapper(name, **AC_spec) for name, AC_spec in AC_specs.items() 
            if config is None or config.getboolean('teamwork', name, fallback=False)}
