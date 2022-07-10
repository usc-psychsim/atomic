from .acwrapper import ACWrapper
from .cmu_wrapper import TEDWrapper, BEARDWrapper
from .cornell_wrapper import ComplianceWrapper
from .gallup_wrapper import GelpWrapper
from .ihmc_wrapper import JAGWrapper
from .rutgers_wrapper import BeliefDiffWrapper
from .ucf_wrapper import PlayerProfileWrapper

import copy
import logging

AC_specs = {
            # 'AC_CMUFMS_TA2_Cognitive': {},
            'ac_cmu_ta2_ted': 
            {'wrapper': TEDWrapper,
             'README': 'https://gitlab.asist.aptima.com/asist/testbed/-/blob/develop/Agents/AC_CMU_TA2_TED/README.md',
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
             'README': 'https://gitlab.asist.aptima.com/asist/testbed/-/blob/develop/Agents/AC_CMU_TA2_BEARD/README.md',
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
             'README': 'https://gitlab.asist.aptima.com/asist/testbed/-/blob/develop/Agents/ac_cornell_ta2_teamtrust/README.md',
             'variables': {'open_requests': {'values': int, 'object': 'pair'},
                           'compliance_overall': {'values': int, 'object': 'pair'},
                           # 'response_start': {'values': int, 'hi': 1, 'object': 'pair'},
                           # 'response_action': {'values': int, 'hi': 1, 'object': 'pair'}
                           }},
            'ac_gallup_ta2_gelp': 
            {'wrapper': GelpWrapper,
             'README': 'https://gitlab.asist.aptima.com/asist/testbed/-/blob/develop/Agents/gallup_agent_gelp/README.md',
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
             'README': 'https://gitlab.asist.aptima.com/asist/testbed/-/blob/develop/Agents/RutgersUtilityAC/README.md',
             'variables': {'wait_time': {'values': bool, 'threshold': 15, 'object': 'player'},
                           'indiv entropy': {'values': float, 'object': 'player'},
                           'marker entropy': {'values': float, 'object': 'player'},
                           'shared entropy': {'values': float, 'object': 'player'}}},
            'ac_ucf_ta2_playerprofiler':
            {'wrapper': PlayerProfileWrapper,
             'README': 'https://gitlab.asist.aptima.com/asist/testbed/-/blob/develop/Agents/AC_UCF_TA2_PlayerProfiler/README.md',
             'variables': {'team-potential-category': {'values': bool, 'object': 'player',
                                                       'influences': {'team monitoring': 1, 'coordination': 1}},
                           'task-potential-category': {'values': bool, 'object': 'player',
                                                       'influences': {'systems monitoring': 1}}}},
            }


def apply_AC_patch(spec, patch):
    for entry in patch:
        table = spec
        for key in entry[:-1]:
            table = table[key]
        table.update(entry[-1])


def make_ac_handlers(config=None, world=None, logger=logging, version=0):
    specs = copy.deepcopy(AC_specs)
    if version >= 1:
        apply_AC_patch(specs, AC_patches[0])
    return {name: AC_spec.get('wrapper', ACWrapper)(name, world, **AC_spec) for name, AC_spec in specs.items() 
            if config is None or config.getboolean('teamwork', name, fallback=True)}
