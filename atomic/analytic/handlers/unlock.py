from ..models.jags.jag import Jag


def handle_proximity(jag_instance: Jag, data):
    # match proximity to known victims
    victim_id = data['victim_id']
    if victim_id != jag_instance.inputs.get('victim-id'):
        return

    # print(f"unlock-victim::handle_proximity {jag_instance.short_string()} {data}")
    player_id = data['participant_id']
    elapsed_ms = data['elapsed_milliseconds']
    players_in_range = data['players_in_range']

    if victim_id != -1:
        # if the awake message exists
        if 'awake' in data:
            awake = data['awake']
            if awake:
                jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
                jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
                jag_instance.update_completion_status(player_id, True, elapsed_ms)
                # print(f"unlock complete for {victim_id} for {player_id}")
            else:
                if players_in_range == 0:
                    jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
                    # print(f"unlock no longer in progress for {victim_id} for {player_id} at {elapsed_ms}")
                if players_in_range >= 1:
                    jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
                    # print(f"unlock in progress for {victim_id} for {player_id} at {elapsed_ms}")
        else:  # else if the awake message does not exist (to handle older proximity messages)
            if players_in_range == 0:
                jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
                # print(f"unlock no longer in progress for {victim_id} for {player_id} at {elapsed_ms}")
            if players_in_range == 1:
                jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
                # print(f"unlock in progress for {victim_id} for {player_id} at {elapsed_ms}")
            elif players_in_range >= 2:
                jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
                jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
                jag_instance.update_completion_status(player_id, True, elapsed_ms)
                # print(f"unlock complete for {victim_id} for {player_id} at {elapsed_ms}")
