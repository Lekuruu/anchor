
from ..constants import RequestPacket
from ..streams   import StreamIn

from typing   import List, Dict, Callable
from datetime import datetime
from abc      import ABC

class BaseHandler(ABC):

    """
    This class will be used as a base for different client handlers.
    """

    packets = RequestPacket

    def __init__(self, player) -> None:
        from bancho.objects.player import Player

        self.player: Player = player
        self.client = self.player.client

    def handle(self, packet_id: int, stream: StreamIn):
        packet = self.packets(packet_id)

        if not (handler := getattr(self, f'handle_{packet.name.lower()}')):
            self.player.logger.warning(
                f'Could not find handler for: "{packet.name}"'
            )
            return
        
        self.player.last_response = datetime.now()

        handler(stream)

    # Responses
    def enqueue_login_reply(self, response: int): ...
    def enqueue_announce(self, message: str): ...
    def enqueue_presence(self, player): ...
    def enqueue_stats(self, player): ...
    def enqueue_privileges(self): ...
    def enqueue_ping(self): ...
    def enqueue_friends(self): ...
    def enqueue_channel(self, channel): ...
    def enqueue_channel_info_end(self): ...
    def enqueue_silence_info(self, remaining_silence: int): ...
    def enqueue_message(self, sender, message: str, target_name: str): ...

    # Requests
    def handle_exit(self, stream: StreamIn): ...
    def handle_change_status(self, stream: StreamIn): ...
    def handle_send_message(self, stream: StreamIn): ...
    def handle_request_status(self, stream: StreamIn): ...
    def handle_pong(self, stream: StreamIn): ...
    def handle_start_spectating(self, stream: StreamIn): ...
    def handle_stop_spectating(self, stream: StreamIn): ...
    def handle_send_frames(self, stream: StreamIn): ...
    def handle_error_report(self, stream: StreamIn): ...
    def handle_cant_spectate(self, stream: StreamIn): ...
    def handle_send_private_message(self, stream: StreamIn): ...
    def handle_part_lobby(self, stream: StreamIn): ...
    def handle_join_lobby(self, stream: StreamIn): ...
    def handle_create_match(self, stream: StreamIn): ...
    def handle_join_match(self, stream: StreamIn): ...
    def handle_leave_match(self, stream: StreamIn): ...
    def handle_match_change_slot(self, stream: StreamIn): ...
    def handle_match_ready(self, stream: StreamIn): ...
    def handle_match_lock(self, stream: StreamIn): ...
    def handle_match_change_settings(self, stream: StreamIn): ...
    def handle_match_start(self, stream: StreamIn): ...
    def handle_match_score_update(self, stream: StreamIn): ...
    def handle_match_complete(self, stream: StreamIn): ...
    def handle_match_change_mods(self, stream: StreamIn): ...
    def handle_match_load_complete(self, stream: StreamIn): ...
    def handle_match_no_beatmap(self, stream: StreamIn): ...
    def handle_match_not_ready(self, stream: StreamIn): ...
    def handle_match_failed(self, stream: StreamIn): ...
    def handle_match_has_beatmap(self, stream: StreamIn): ...
    def handle_match_skip(self, stream: StreamIn): ...
    def handle_join_channel(self, stream: StreamIn): ...
    def handle_beatmap_info(self, stream: StreamIn): ...
    def handle_match_transfer_host(self, stream: StreamIn): ...
    def handle_add_friend(self, stream: StreamIn): ...
    def handle_remove_friend(self, stream: StreamIn): ...
    def handle_match_change_team(self, stream: StreamIn): ...
    def handle_leave_channel(self, stream: StreamIn): ...
    def handle_receive_updates(self, stream: StreamIn): ...
    def handle_set_away_message(self, stream: StreamIn): ...
    def handle_irc_only(self, stream: StreamIn): ...
    def handle_stats_request(self, stream: StreamIn): ...
    def handle_match_invite(self, stream: StreamIn): ...
    def handle_match_change_password(self, stream: StreamIn): ...
    def handle_tournament_match_info(self, stream: StreamIn): ...
    def handle_presence_request(self, stream: StreamIn): ...
    def handle_presence_request_all(self, stream: StreamIn): ...
    def handle_change_friendonly_dms(self, stream: StreamIn): ...
