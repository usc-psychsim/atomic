GET_IN_RANGE = {
    'urn': 'urn:ihmc:asist:get-in-range',
    'name': 'Get in range',
    'children': [],
}

SEARCH_AREA = {
    'urn': 'urn:ihmc:asist:search-area',
    'name': "Search area",
    'children': [
        {'urn': GET_IN_RANGE['urn']},
        # {'urn': SEARCH_AREA['urn']} # this sub search can be dynamically added at runtime
    ],
    "connector": {
        "execution": "node.execution.sequential",
        "operator": "node.operator.and"
    }
}

RESCUE_VICTIM = {
    'urn': 'urn:ihmc:asist:rescue-victim',
    'name': "Rescue Victim",
    'children': [
        {'urn': 'urn:ihmc:asist:access-victim'},
        {'urn': 'urn:ihmc:asist:triage-and-evacuate'}
    ],
    "connector": {
        "execution": "node.execution.sequential",
        "operator": "node.operator.and"
    }
}

ACCESS_VICTIM = {
    'urn': 'urn:ihmc:asist:access-victim',
    'name': "Access Victim",
    'children': [
        {'urn': 'urn:ihmc:asist:check-if-unlocked'},
        {'urn': 'urn:ihmc:asist:unlock-victim'}
    ],
    "connector": {
        "execution": "node.execution.parallel",
        "operator": "node.operator.or"
    }
}

TRIAGE_AND_EVACUATE = {
    'urn': 'urn:ihmc:asist:triage-and-evacuate',
    'name': "Triage and Evacuate",
    'children': [
        {'urn': 'urn:ihmc:asist:triage-victim'},
        {'urn': 'urn:ihmc:asist:evacuate-victim'}
    ],
    "connector": {
        "execution": "node.execution.parallel",
        "operator": "node.operator.and"
    }
}

TRIAGE_VICTIM = {
    'urn': 'urn:ihmc:asist:triage-victim',
    'name': "Triage Victim",
    'children': [
        {'urn': 'urn:ihmc:asist:stabilize'}
    ],
    "connector": {
        "execution": "node.execution.sequential",
        "operator": "node.operator.and"
    }
}

EVACUATE_VICTIM = {
    'urn': 'urn:ihmc:asist:evacuate-victim',
    'name': "Evacuate Victim",
    'children': [
        {'urn': 'urn:ihmc:asist:determine-triage-area'},
        {'urn': 'urn:ihmc:asist:move-victim-to-triage-area'}
    ],
    "connector": {
        "execution": "node.execution.sequential",
        "operator": "node.operator.and"
    }
}

DETERMINE_TRIAGE_AREA = {
    'urn': 'urn:ihmc:asist:determine-triage-area',
    'name': "Determine Triage Area",
    'children': [
        {'urn': 'urn:ihmc:asist:diagnose'}
    ],
    "connector": {
        "execution": "node.execution.sequential",
        "operator": "node.operator.and"
    }
}

MOVE_VICTIM_TO_TRIAGE_AREA = {
    'urn': 'urn:ihmc:asist:move-victim-to-triage-area',
    'name': "Move Victim To Triage Area",
    'children': [
        {'urn': 'urn:ihmc:asist:relocate-victim'},
        {'urn': 'urn:ihmc:asist:at-proper-triage-area'}
    ],
    "connector": {
        "execution": "node.execution.parallel",
        "operator": "node.operator.and"
    }
}

RELOCATE_VICTIM = {
    'urn': 'urn:ihmc:asist:relocate-victim',
    'name': "Relocate Victim",
    'children': [
        # {'urn': 'urn:ihmc:asist:determine-victim-destination'},
        {'urn': 'urn:ihmc:asist:pick-up-victim'},
        {'urn': 'urn:ihmc:asist:drop-off-victim'}
    ],
    "connector": {
        "execution": "node.execution.sequential",
        "operator": "node.operator.and"
    }
}

DETERMINE_VICTIM_DESTINATION = {
    'urn': 'urn:ihmc:asist:determine-victim-destination',
    'name': "Determine Destination for Victim",
    'children': []
}

AT_PROPER_TRIAGE_AREA = {
    'urn': 'urn:ihmc:asist:at-proper-triage-area',
    'name': "At Proper Triage Area",
    'children': []
}

PICK_UP_VICTIM = {
    'urn': 'urn:ihmc:asist:pick-up-victim',
    'name': "Pick Up Victim",
    'children': []
}

DROP_OFF_VICTIM = {
    'urn': 'urn:ihmc:asist:drop-off-victim',
    'name': "Drop Off Victim",
    'children': []
}

CHECK_IF_UNLOCKED = {
    'urn': 'urn:ihmc:asist:check-if-unlocked',
    'name': "Check If Unlocked",
    'children': []
}

UNLOCK_VICTIM = {
    'urn': 'urn:ihmc:asist:unlock-victim',
    'name': "Unlock Victim",
    'children': []
}

STABILIZE = {
    'urn': 'urn:ihmc:asist:stabilize',
    'name': "Stabilize",
    'children': []
}

DIAGNOSE = {
    'urn': 'urn:ihmc:asist:diagnose',
    'name': "Diagnose",
    'children': []
}

# GET_IN_RANGE = {
#     'urn': 'urn:ihmc:asist:get-in-range',
#     'name': "Get In Range",
#     'children': [
#         {'urn': 'urn:ihmc:asist:find-path'},
#         {'urn': 'urn:ihmc:asist:go-to'}
#     ],
#     "connector": {
#         "execution": "node.execution.sequential",
#         "operator": "node.operator.and"
#     }
# }
#
# FIND_PATH = {
#     'urn': 'urn:ihmc:asist:find-path',
#     'name': "Find Path",
#     'children': [
#         {'urn': 'urn:ihmc:asist:check-if-clear'},
#         {'urn': 'urn:ihmc:asist:clear-path'}
#     ],
#     "connector": {
#         "execution": "node.execution.parallel",
#         "operator": "node.operator.or"
#     }
# }
#
# GO_TO = {
#     'urn': 'urn:ihmc:asist:go-to',
#     'name': "Go To",
#     'children': []
# }
#
# CHECK_IF_CLEAR = {
#     'urn': 'urn:ihmc:asist:check-if-clear',
#     'name': "Check If Clear",
#     'children': []
# }
#
CLEAR_PATH = {
    'urn': 'urn:ihmc:asist:clear-path',
    'name': "Clear Path",
    'children': []
}

ASIST_JAGS = [
    RESCUE_VICTIM,
    ACCESS_VICTIM,
    CHECK_IF_UNLOCKED,
    UNLOCK_VICTIM,
    TRIAGE_AND_EVACUATE,
    TRIAGE_VICTIM,
    STABILIZE,
    DIAGNOSE,
    EVACUATE_VICTIM,
    DETERMINE_TRIAGE_AREA,
    MOVE_VICTIM_TO_TRIAGE_AREA,
    RELOCATE_VICTIM,
    DETERMINE_VICTIM_DESTINATION,
    PICK_UP_VICTIM,
    DROP_OFF_VICTIM,
    SEARCH_AREA,
    GET_IN_RANGE,
    AT_PROPER_TRIAGE_AREA,
    # GET_IN_RANGE,
    # FIND_PATH,
    # GO_TO,
    # CHECK_IF_CLEAR,
    CLEAR_PATH
]
