from ..models.jags.jag import Jag


def handle_triage(jag_instance: Jag, data):
    victim_id = data['victim_id']
    if victim_id != jag_instance.inputs.get('victim-id'):
        return

    player_id = data['participant_id']
    elapsed_ms = data['elapsed_milliseconds']
    triage_state = data['triage_state']

    if triage_state == "IN_PROGRESS":
        jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
        jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
        jag_instance.update_completion_status(player_id, True, elapsed_ms)
