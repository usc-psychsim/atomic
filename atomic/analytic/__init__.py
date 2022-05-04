from .acwrapper import ACWrapper
from .cmu_wrapper import TEDWrapper, BEARDWrapper
from .cornell_wrapper import ComplianceWrapper
from .gallup_wrapper import GelpWrapper
from .ihmc_wrapper import JAGWrapper
from .rutgers_wrapper import BeliefDiffWrapper
from .ucf_wrapper import PlayerProfileWrapper


AC_specs = {
            # 'AC_CMUFMS_TA2_Cognitive': {},
            'ac_cmu_ta2_ted': 
            {'wrapper': TEDWrapper,
             'variables': {'comms_equity': {'object': 'team', 'values': bool, 'threshold': 100,
                                            'influences': {'coordination': 1}},
                           'comms_total_words': {'object': 'team', 'values': bool, 'threshold': 100,
                                                 'influences': {'team monitoring': 1}},
                           'dig_rubble_count': {'object': 'team', 'values': bool, 'threshold': 0},
                           'explore_count': {'object': 'team', 'values': bool, 'threshold': 0},
                           'inaction_stand_s': {'object': 'team', 'values': bool, 'threshold': 5,
                                                'influences': {'systems monitoring': -1}},
                           'move_victim_count': {'object': 'team', 'values': bool, 'threshold': 0},
                           'process_coverage': {'object': 'team', 'values': bool, 'threshold': 0},
                           'process_effort_agg': {'object': 'team', 'values': bool, 'threshold': 0.5,
                                                  'influences': {'motivating': 1}},
                           'process_skill_use_rel': {'object': 'team', 'values': bool, 'threshold': 0.5},
                           'process_workload_burnt_agg': {'object': 'team', 'values': float},
                           'team_score': {'object': 'team', 'values': int},
                           'team_score_agg': {'object': 'team', 'values': int},
                           'triage_count': {'object': 'team', 'values': bool, 'threshold': 0},
                           }},
            'ac_cmu_ta2_beard':
            {'wrapper': BEARDWrapper,
             'variables': {'anger': {'object': 'player', 'values': bool, 'threshold': 1.5,
                                     'influences': {'affect management': -1}},
                           'anxiety': {'object': 'player', 'values': bool, 'threshold': 2,
                                       'influences': {'affect management': -1}},
                           'gaming_experience': {'object': 'player', 'values': bool, 'threshold': 4,
                                                 'influences': {'systems monitoring': 1}},
                           # 'marking_skill': {'object': 'player', 'values': bool, 'threshold': 3},
                           'mission_knowledge': {'object': 'player', 'values': bool, 'threshold': 30},
                           'rmie': {'object': 'player', 'values': bool, 'threshold': 0.75,
                                    'influences': {'team monitoring': 1}},
                           'sbsod': {'object': 'player', 'values': bool, 'threshold': 5,
                                     'influences': {'systems monitoring': 1}},
                           # 'transporting_skill': {'object': 'player', 'values': bool, 'threshold': 4},
                           'walking_skill': {'object': 'player', 'values': bool, 'threshold': 0.25},
                           }},
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
             'variables': {'Leadership': {'values': float, 'object': 'player'}}},
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
             'variables': {'indiv entropy': {'values': float, 'object': 'player'},
                           'marker entropy': {'values': float, 'object': 'player'},
                           'shared entropy': {'values': float, 'object': 'player'}}},
            'ac_ucf_ta2_playerprofiler':
            {'wrapper': PlayerProfileWrapper,
             'variables': {'team-potential-category': {'values': bool, 'object': 'player',
                                                       'influences': {'team monitoring': 1, 'coordination': 1}},
                           'task-potential-category': {'values': bool, 'object': 'player',
                                                       'influences': {'systems monitoring': 1}}}},
            }


def make_ac_handlers(config=None, world=None):
    return {name: AC_spec.get('wrapper', ACWrapper)(name, world, **AC_spec) for name, AC_spec in AC_specs.items() 
            if config is None or config.getboolean('teamwork', name, fallback=False)}
