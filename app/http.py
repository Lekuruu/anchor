
from __future__ import annotations

from app.common.constants import ANCHOR_WEB_RESPONSE
from app.common.streams import StreamIn
from app.objects.client import OsuClient
from app.objects.player import Player
from app.objects import OsuClient

from twisted.web.resource import Resource
from twisted.web.http import Request
from queue import Queue

import config
import utils
import gzip
import uuid
import app

class HttpPlayer(Player):
    def __init__(self, address: str, port: int) -> None:
        super().__init__(address, port)
        self.queue = Queue()
        self.token = ""

    @property
    def connected(self) -> bool:
        return bool(self.token)

    def enqueue(self, data: bytes):
        self.queue.put(data)

    def dequeue(self) -> bytes:
        data = b''
        while not self.queue.empty():
            data += self.queue.get()
        return data

    def login_received(self, username: str, md5: str, client: OsuClient):
        super().login_received(username, md5, client)

        if self.logged_in:
            self.token = str(uuid.uuid4())

    def close_connection(self, error: Exception | None = None):
        if error:
            self.send_error(message=str(error) if config.DEBUG else None)
            self.logger.warning(f'Closing connection -> <{self.address}>')
        else:
            self.logger.info(f'Closing connection -> <{self.address}>')

        self.token = ""
        super().connectionLost(error)

class HttpBanchoProtocol(Resource):
    isLeaf = True

    def __init__(self):
        self.player: HttpPlayer | None = None
        self.children = {}

    def handle_login_request(self, request: Request):
        request.setHeader('cho-token', '')

        username, password, client_data = (
            request.content.read().decode().splitlines()
        )

        ip_address = utils.resolve_ip_address(request)
        client = OsuClient.from_string(client_data, ip_address)

        try:
            self.player = HttpPlayer(ip_address, request.getClientAddress().port)
            self.player.login_received(username, password, client)
        except Exception as e:
            request.setResponseCode(500)
            self.player.logger.error(
                f'Login failed: {e}', exc_info=e
            )
            return

        request.setResponseCode(200)
        request.setHeader('cho-token', self.player.token)
        request.write(self.player.dequeue())

    def handle_request(self, request: Request):
        stream = StreamIn(request.content.read())

        try:
            while not stream.eof():
                packet = stream.u16()
                compression = stream.bool()
                payload = stream.read(stream.u32())

                if compression:
                    payload = gzip.decompress(payload)

                self.player.packet_received(
                    packet_id=packet,
                    stream=StreamIn(payload)
                )
        except Exception as e:
            request.setResponseCode(500)
            self.player.send_error()
            self.player.logger.error(
                f'Failed to parse packet: {e}', exc_info=e
            )

        request.write(self.player.dequeue())

    def render_GET(self, request: Request):
        request.setHeader('content-type', 'text/html; charset=utf-8')
        request.setHeader('server', 'bancho')
        return ANCHOR_WEB_RESPONSE.encode('utf-8')

    def render_POST(self, request: Request):
        request.setHeader('server', 'bancho')
        request.setHeader('cho-protocol', '18')

        if not (osu_token := request.getHeader('osu-token')):
            return self.handle_login_request(request)

        if not (player := app.session.players.by_token(osu_token)):
            # TODO: Send restart packet
            request.setResponseCode(403)
            request.setHeader('cho-token', '')
            return

        self.player = player
        return self.handle_request(request)
