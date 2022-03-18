from ..models.jags.jag import Jag


def handle_victim_evacuated(jag_instance: Jag, data):
    victim_id = data['victim_id']
    if victim_id != jag_instance.inputs.get('victim-id'):
        return

    # print(f"at_proper_triage_area::handle_victim_evacuated {jag_instance.short_string()}")  # {data}")
    player_id = data['participant_id']
    elapsed_ms = data['elapsed_milliseconds']
    success = data['success']
    if success:
        jag_instance.update_preparing(player_id, player_id, 1.0, elapsed_ms)
        jag_instance.update_preparing(player_id, player_id, 0.0, elapsed_ms)
        jag_instance.update_addressing(player_id, player_id, 1.0, elapsed_ms)
        jag_instance.update_addressing(player_id, player_id, 0.0, elapsed_ms)
        jag_instance.update_completion_status(player_id, success, elapsed_ms)
