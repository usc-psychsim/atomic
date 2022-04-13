from ..models.jags.jag import Jag


def handle_triage(jag_instance: Jag, data):
    victim_id = data['victim_id']
    if victim_id != jag_instance.inputs.get('victim-id'):
        return

    # print(f"stabilize::handle_triage {jag_instance.short_string()} {data}")

    player_id = data['participant_id']
    elapsed_ms = data['elapsed_milliseconds']
    triage_state = data['triage_state']

    is_addressing = jag_instance.is_addressing(player_id)

    if triage_state == "IN_PROGRESS":
        jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
        # if is_addressing than we received two messages and can ignore

    if triage_state == "SUCCESSFUL":
        if is_addressing:  # normal messaging
            jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
            jag_instance.update_completion_status(player_id, True, elapsed_ms)
        else:  # must have missed a message
            print(f"{victim_id} missed an in progress message but done with {jag_instance.short_string()}")
            jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
            jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
            jag_instance.update_completion_status(player_id, True, elapsed_ms)

    if triage_state == "UNSUCCESSFUL":
        if is_addressing:  # normal messaging
            jag_instance.update_addressing(player_id, player_id, 0.5, elapsed_ms)
        else:  # must have missed a message
            print(f"{victim_id} missed an in progress message but still not done with {jag_instance.short_string()}")
            jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
            jag_instance.update_addressing(player_id, player_id, 0.5, elapsed_ms)


