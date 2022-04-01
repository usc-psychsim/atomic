from ..models.jags.jag import Jag


def handle_location_update(jag_instance: Jag, data):
    # only handles area based get-in-range
    if 'area' not in jag_instance.inputs:
        return

    area_id = jag_instance.inputs.get('area')

    if 'locations' not in data:
        return

    for location in data['locations']:
        if location['id'] != area_id:
            continue

        player_id = data['participant_id']
        elapsed_ms = data['elapsed_milliseconds']
        if elapsed_ms < 0.0:  # ignore negative times, they should only happen after the trial has ended
            return

        jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
        jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
        jag_instance.update_completion_status(player_id, True, elapsed_ms)
        break


def handle_proximity(jag_instance: Jag, data):
    print(f"get-in-range::handle_proximity {jag_instance.short_string()}")  # {data}")
    victim_id = data['victim_id']
    if victim_id != jag_instance.inputs.get('victim-id'):
        return

    player_id = data['participant_id']
    elapsed_ms = data['elapsed_milliseconds']
    players_in_range = data['players_in_range']
    if victim_id != -1:
        if players_in_range > 0:
            jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
            jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
            jag_instance.update_completion_status(player_id, True, elapsed_ms)
