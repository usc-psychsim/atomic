from ..models.jags.jag import Jag


def handle_proximity(jag_instance: Jag, data):
    victim_id = data['victim_id']
    if victim_id != jag_instance.inputs.get('victim-id'):
        return

    # print(f"unlock::handle_proximity {jag_instance.short_string()}")  # {data}")

    player_id = data['participant_id']
    elapsed_ms = data['elapsed_milliseconds']
    players_in_range = data['players_in_range']
    if victim_id != -1:
        if players_in_range < 2:
            jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
        else:
            jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
            jag_instance.update_completion_status(player_id, True, elapsed_ms)
