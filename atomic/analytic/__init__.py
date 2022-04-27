import operator

from .acwrapper import ACWrapper
from .cmu_wrapper import TEDWrapper, BEARDWrapper
from .cornell_wrapper import ComplianceWrapper
from .gallup_wrapper import GelpWrapper, GOLDWrapper
from .ihmc_wrapper import JAGWrapper
from .rutgers_wrapper import BeliefDiffWrapper
from .ucf_wrapper import PlayerProfileWrapper


AC_specs = {
            # 'AC_CMUFMS_TA2_Cognitive': {},
            'ac_cmu_ta2_ted': 
            {'wrapper': TEDWrapper,
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
            {'wrapper': BEARDWrapper,
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
            # 'AC_CORNELL_TA2_ASI-FACEWORK': {},
            'AC_CORNELL_TA2_TEAMTRUST':
            {'wrapper': ComplianceWrapper,
             'variables': {'open requests': {'values': int, 'object': 'pair'},
                           'compliance': {'values': int, 'object': 'pair'},
                           'compliance rate': {'values': int, 'hi': 1, 'object': 'pair'},
                           'response start': {'values': int, 'hi': 1, 'object': 'pair'},
                           'response action': {'values': int, 'hi': 1, 'object': 'pair'}}},
            'ac_gallup_ta2_gelp': 
            {'wrapper': GelpWrapper,
             'variables': {'leadership': {'values': int, 'hi': 1, 'object': 'player'}}},
            # 'ac_gallup_ta2_gold':
            # {'wrapper': GOLDWrapper,
            # },
            # 'AC_IHMC_TA2_Dyad-Reporting': {},
            # 'AC_IHMC_TA2_Location-Monitor': {},
            # 'AC_IHMC_TA2_Player-Proximity': {},
            'ac_ihmc_ta2_joint-activity-interdependence':
            {'wrapper': JAGWrapper},
            'AC_Rutgers_TA2_Utility':
            {'wrapper': BeliefDiffWrapper,
             'variables': {'indiv entropy': {'values': int, 'hi': 1, 'object': 'player'},
                           'marker entropy': {'values': int, 'hi': 1, 'object': 'player'}}},
            'ac_ucf_ta2_playerprofiler':
            {'wrapper': PlayerProfileWrapper,
             'variables': {'team-potential-category': {'values': int, 'hi': 1, 'object': 'player', 'mapping': {'HighTeam': 1, 'LowTeam': 0},},
                           'task-potential-category': {'values': int, 'hi': 1, 'object': 'player', 'mapping': {'HighTask': 1, 'LowTask': 0}}}},
            }


def make_ac_handlers(config=None):
    return {name: AC_spec.get('wrapper', ACWrapper)(name, **AC_spec) for name, AC_spec in AC_specs.items() 
            if config is None or config.getboolean('teamwork', name, fallback=False)}
