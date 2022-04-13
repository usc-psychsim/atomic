from ..models.jags.jag import Jag


def handle_rubble_destroyed(jag_instance: Jag, data):
    # print(f"clear_path::handle_rubble_destroyed {jag_instance.short_string()} {data}")
    player_id = data['participant_id']
    elapsed_ms = data['elapsed_milliseconds']
    jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)




