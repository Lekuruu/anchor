
from app.common.constants import (
    PresenceFilter,
    Permissions,
    LoginError,
    QuitState,
    GameMode
)

from app.common.objects import (
    ReplayFrameBundle,
    UserPresence,
    StatusUpdate,
    UserStats,
    UserQuit,
    Message,
    Channel
)

from app.common.database.repositories import users, histories, stats
from app.common.cache import leaderboards

from app.protocol import BanchoProtocol, IPAddress
from app.common.streams import StreamIn

from app.common.database import DBUser, DBStats
from app.objects import OsuClient, Status

from typing import Optional, Callable, Tuple, List, Dict, Set
from datetime import datetime
from enum import Enum
from copy import copy

from twisted.internet.error import ConnectionDone
from twisted.internet.address import IPv4Address
from twisted.python.failure import Failure

from app.clients.packets import PACKETS
from app.clients import (
    DefaultResponsePacket,
    DefaultRequestPacket
)

import traceback
import hashlib
import logging
import config
import bcrypt
import utils
import time
import app

class Player(BanchoProtocol):
    def __init__(self, address: IPAddress) -> None:
        self.is_local = utils.is_localip(address.host)
        self.logger = logging.getLogger(address.host)
        self.address = address

        self.away_message: Optional[str] = None
        self.client: Optional[OsuClient] = None
        self.object: Optional[DBUser] = None
        self.stats:  Optional[List[DBStats]] = None
        self.status = Status()

        self.id = -1
        self.name = ""

        self.request_packets = DefaultRequestPacket
        self.packets = DefaultResponsePacket
        self.decoders: Dict[Enum, Callable] = {}
        self.encoders: Dict[Enum, Callable] = {}

        self.channels: Set[Channel] = set()
        self.filter = PresenceFilter.All

        from .collections import Players
        from .multiplayer import Match
        from .channel import Channel

        self.spectators = Players()
        self.spectating: Optional[Player] = None
        self.spectator_chat: Optional[Channel] = None

        self.in_lobby = False
        self.match: Optional[Match] = None
        self.last_response = time.time()

    def __repr__(self) -> str:
        return f'<Player ({self.id})>'

    @classmethod
    def bot_player(cls):
        player = Player(
            IPv4Address(
                'TCP',
                '127.0.0.1',
                1337
            )
        )

        player.object = users.fetch_by_id(1)
        player.client = OsuClient.empty()

        player.id = -player.object.id # Negative user id -> IRC Player
        player.name = player.object.name
        player.stats  = player.object.stats

        player.client.ip.country_code = "OC"
        player.client.ip.city = "w00t p00t!"

        return player

    @property
    def is_bot(self) -> bool:
        return True if self.id == -1 else False

    @property
    def silenced(self) -> bool:
        return False # TODO

    @property
    def supporter(self) -> bool:
        return True # TODO

    @property
    def restricted(self) -> bool:
        if not self.object:
            return False
        return self.object.restricted

    @property
    def current_stats(self) -> Optional[DBStats]:
        for stats in self.stats:
            if stats.mode == self.status.mode.value:
                return stats
        return None

    @property
    def permissions(self) -> Optional[Permissions]:
        if not self.object:
            return
        return Permissions(self.object.permissions)

    @property
    def friends(self) -> List[int]:
        return [
            rel.target_id
            for rel in self.object.relationships
            if rel.status == 0
        ]

    @property
    def user_presence(self) -> Optional[UserPresence]:
        try:
            return UserPresence(
                self.id,
                False,
                self.name,
                self.client.utc_offset,
                self.client.ip.country_index,
                self.permissions,
                self.status.mode,
                self.client.ip.longitude,
                self.client.ip.latitude,
                self.current_stats.rank
            )
        except AttributeError:
            return None

    @property
    def user_stats(self) -> Optional[UserStats]:
        try:
            return UserStats(
                self.id,
                StatusUpdate(
                    self.status.action,
                    self.status.text,
                    self.status.mods,
                    self.status.mode,
                    self.status.checksum,
                    self.status.beatmap
                ),
                self.current_stats.rscore,
                self.current_stats.tscore,
                self.current_stats.acc,
                self.current_stats.playcount,
                self.current_stats.rank,
                self.current_stats.pp,
            )
        except AttributeError:
            return None

    def connectionLost(self, reason: Failure = Failure(ConnectionDone())):
        app.session.players.remove(self)

        for channel in copy(self.channels):
            channel.remove(self)

        app.session.players.send_packet(
            self.packets.USER_QUIT,
            UserQuit(
                self.id,
                QuitState.Gone # TODO: IRC
            )
        )

        # TODO: Remove spectator channel from collection
        # TODO: Remove from match

        super().connectionLost(reason)

    def reload_object(self) -> DBUser:
        """Reload player stats from database"""
        self.object = users.fetch_by_id(self.id)
        self.stats = self.object.stats

        self.update_leaderboard_stats()
        self.reload_rank()

        return self.object

    def reload_rank(self) -> None:
        """Reload player rank from cache and update it if needed"""
        cached_rank = leaderboards.global_rank(self.id, self.status.mode.value)

        if cached_rank != self.current_stats.rank:
            self.current_stats.rank = cached_rank

            # Update rank in database
            stats.update(
                self.id,
                self.status.mode.value,
                {
                    'rank': cached_rank
                }
            )

            # Update rank history
            histories.update_rank(self.current_stats, self.object.country)

    def update_leaderboard_stats(self) -> None:
        leaderboards.update(
            self.id,
            self.status.mode.value,
            self.current_stats.pp,
            self.current_stats.rscore,
            self.object.country,
        )

    def close_connection(self, error: Optional[Exception] = None):
        self.connectionLost()
        super().close_connection(error)

    def send_error(self, reason=-5, message=""):
        if self.encoders and message:
            self.send_packet(
                self.packets.ANNOUNCE,
                message
            )

        self.send_packet(
            self.packets.LOGIN_REPLY,
            reason
        )

    def send_packet(self, packet_type: Enum, *args):
        if self.is_bot:
            return

        return super().send_packet(
            packet_type,
            self.encoders,
            *args
        )

    def login_failed(self, reason = LoginError.ServerError, message = ""):
        self.send_error(reason.value, message)
        self.close_connection()

    def get_client(self, version: int) -> Tuple[Dict[Enum, Callable], Dict[Enum, Callable]]:
        """Figure out packet sender/decoder, closest to version of client"""

        decoders, encoders = PACKETS[
            min(
                PACKETS.keys(),
                key=lambda x:abs(x-version)
            )
        ]

        return decoders, encoders

    def login_received(self, username: str, md5: str, client: OsuClient):
        self.logger.info(f'Login attempt as "{username}" with {client.version.string}.')
        self.logger.name = f'Player "{username}"'
        self.last_response = time.time()

        # TODO: Set packet enums

        # Get decoders and encoders
        self.decoders, self.encoders = self.get_client(client.version.date)

        # Send protocol version
        self.send_packet(self.packets.PROTOCOL_VERSION, config.PROTOCOL_VERSION)

        # Check adapters md5
        adapters_hash = hashlib.md5(client.hash.adapters.encode()).hexdigest()

        # TODO: Store login attempt in database

        if adapters_hash != client.hash.adapters_md5:
            self.transport.write('no.\r\n')
            self.close_connection()
            return

        if not (user := users.fetch_by_name(username)):
            self.logger.warning('Login Failed: User not found')
            self.login_failed(LoginError.Authentication)
            return

        if not bcrypt.checkpw(md5.encode(), user.bcrypt.encode()):
            self.logger.warning('Login Failed: Authentication error')
            self.login_failed(LoginError.Authentication)
            return

        if user.restricted:
            # TODO: Check ban time
            self.logger.warning('Login Failed: Restricted')
            self.login_failed(LoginError.Banned)
            return

        if not user.activated:
            self.logger.warning('Login Failed: Not activated')
            self.login_failed(LoginError.NotActivated)
            return

        if (other_user := app.session.players.by_id(user.id)):
            other_user.enqueue_announcement('\n'.join([
                'Another player has logged in to your account, from another location.',
                'Please change your password immediately, if you think this is an error!'
            ]))
            other_user.close_connection()

        # TODO: Tournament clients

        self.id = user.id
        self.name = user.name
        self.stats = user.stats
        self.object = user

        self.status.mode = GameMode(self.object.preferred_mode)

        if not self.stats:
            self.create_stats()
            self.reload_object()
            self.enqueue_silence_info(-1)

        self.update_leaderboard_stats()
        self.login_success()

    def login_success(self):
        from .channel import Channel

        self.spectator_chat = Channel(
            name=f'#spec_{self.id}',
            topic=f"{self.name}'s spectator channel",
            owner=self.name,
            read_perms=1,
            write_perms=1,
            public=False
        )

        # TODO: Add to channel collection

        # Update latest activity
        self.update_activity()

        # Protocol Version
        self.send_packet(self.packets.PROTOCOL_VERSION, 18)

        # User ID
        self.send_packet(self.packets.LOGIN_REPLY, self.id)

        # Menu Icon
        self.send_packet(
            self.packets.MENU_ICON,
            config.MENUICON_IMAGE,
            config.MENUICON_URL
        )

        # Permissions
        self.send_packet(
            self.packets.LOGIN_PERMISSIONS,
            self.permissions
        )

        # Presence
        self.enqueue_presence(self)
        self.enqueue_stats(self)

        # Bot presence
        self.enqueue_presence(app.session.bot_player)

        # Friends
        self.enqueue_friends()

        # Append to player collection
        app.session.players.append(self)

        # Enqueue other players
        self.enqueue_players(app.session.players)

        for channel in app.session.channels.public:
            if channel.can_read(self.permissions):
                self.enqueue_channel(channel)

        self.send_packet(self.packets.CHANNEL_INFO_COMPLETE)

        # TODO: Remaining silence

    def packet_received(self, packet_id: int, stream: StreamIn):
        self.last_response = time.time()

        if self.is_bot:
            return

        try:
            packet = self.request_packets(packet_id)

            decoder = self.decoders[packet]
            args = decoder(stream)

            self.logger.debug(
                f'-> {packet.name}: {args}'
            )
        except KeyError as e:
            self.logger.error(
                f'Could not find decoder for "{packet.name}": {e}'
            )
            return
        except ValueError as e:
            self.logger.error(
                f'Could not find packet with id "{packet_id}": {e}'
            )
            return

        try:
            handler_function = app.session.handlers[packet]
            handler_function(
               *[self, args] if args != None else
                [self]
            )
        except Exception as e:
            if config.DEBUG: traceback.print_exc()
            self.logger.error(f'Failed to execute handler for packet "{packet.name}": {e}')

    def create_stats(self):
        self.stats = [stats.create(self.id, mode) for mode in range(4)]

    def update_activity(self):
        users.update(
            user_id=self.id,
            updates={
                'latest_activity': datetime.now()
            }
        )

    def enqueue_ping(self):
        self.send_packet(self.packets.PING)

    def enqueue_player(self, player):
        self.send_packet(
            self.packets.USER_PRESENCE_SINGLE,
            player.id
        )

    def enqueue_players(self, players):
        n = max(1, 150)

        # Split players into chunks to avoid any buffer overflows
        for chunk in (players[i:i+n] for i in range(0, len(players), n)):
            self.send_packet(
                self.packets.USER_PRESENCE_BUNDLE,
                [player.id for player in chunk]
            )

    def enqueue_presence(self, player):
        self.send_packet(
            self.packets.USER_PRESENCE,
            player.user_presence
        )

    def enqueue_stats(self, player):
        self.send_packet(
            self.packets.USER_STATS,
            player.user_stats
        )

    def enqueue_message(self, message: Message):
        self.send_packet(
            self.packets.SEND_MESSAGE,
            message
        )

    def enqueue_channel(self, channel: Channel, autojoin: bool = False):
        self.send_packet(
            self.packets.CHANNEL_AVAILABLE if not autojoin else \
            self.packets.CHANNEL_AVAILABLE_AUTOJOIN,
            channel
        )

    def join_success(self, name: str):
        self.send_packet(
            self.packets.CHANNEL_JOIN_SUCCESS,
            name
        )

    def revoke_channel(self, name: str):
        self.send_packet(
            self.packets.CHANNEL_REVOKED,
            name
        )

    def enqueue_blocked_dms(self, username: str):
        self.send_packet(
            self.packets.USER_DM_BLOCKED,
            Message(
                '',
                '',
                username,
                -1
            )
        )

    def enqueue_silenced_target(self, username: str):
        self.send_packet(
            self.packets.TARGET_IS_SILENCED,
            Message(
                '',
                '',
                username,
                -1
            )
        )

    def enqueue_silenced_user(self, user_id: int):
        self.send_packet(
            self.packets.USER_SILENCED,
            user_id
        )

    def enqueue_silence_info(self, remaining_time: int):
        self.send_packet(
            self.packets.SILENCE_INFO,
            remaining_time
        )

    def enqueue_friends(self):
        self.send_packet(
            self.packets.FRIENDS_LIST,
            self.friends
        )

    def enqueue_spectator(self, player_id: int):
        self.send_packet(
            self.packets.SPECTATOR_JOINED,
            player_id
        )

    def enqueue_spectator_left(self, player_id: int):
        self.send_packet(
            self.packets.SPECTATOR_LEFT,
            player_id
        )

    def enqueue_fellow_spectator(self, player_id: int):
        self.send_packet(
            self.packets.FELLOW_SPECTATOR_JOINED,
            player_id
        )

    def enqueue_fellow_spectator_left(self, player_id: int):
        self.send_packet(
            self.packets.FELLOW_SPECTATOR_LEFT,
            player_id
        )

    def enqueue_cant_spectate(self, player_id: int):
        self.send_packet(
            self.packets.CANT_SPECTATE,
            player_id
        )

    def enqueue_frames(self, bundle: ReplayFrameBundle):
        self.send_packet(
            self.packets.SPECTATE_FRAMES,
            bundle
        )

    def enqueue_lobby_join(self, player_id: int):
        self.send_packet(
            self.packets.LOBBY_JOIN,
            player_id
        )

    def enqueue_lobby_part(self, player_id: int):
        self.send_packet(
            self.packets.LOBBY_PART,
            player_id
        )

    def enqueue_invite(self, message: Message):
        self.send_packet(
            self.packets.INVITE,
            message
        )

    def enqueue_announcement(self, message: str):
        self.send_packet(
            self.packets.ANNOUNCE,
            message
        )
