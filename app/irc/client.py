
from twisted.words.protocols.irc import IRC, IRCBadMessage, IRCPasswordMismatch
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.error import ConnectionDone
from twisted.python.failure import Failure
from twisted.protocols import basic
from typing import Union, List

from app.objects.channel import Channel

import app.irc as irc
import logging

IPAddress = Union[IPv4Address, IPv6Address]

class IRCClient(IRC):
    def __init__(self, address: IPAddress):
        self.logger = logging.getLogger(address.host)
        self.channels: List[Channel] = []
        self.address = address

    def connectionMade(self):
        super().connectionMade()
        self.logger.info(
            f'-> <{self.address.host}:{self.address.port}>'
        )

    def connectionLost(self, reason: Failure = ...):
        if reason.type != ConnectionDone:
            self.logger.warning(
                f'<{self.address.host}> -> Lost connection: "{reason.getErrorMessage()}".'
            )
            return

        self.logger.info(
            f'<{self.address.host}> -> Connection done.'
        )

    def handleCommand(self, command, prefix, params):
        if not (handler := irc.handlers.HANDLERS.get(command)):
            self.logger.warning(f'Could not find handler for "{command}"!')
            return

        self.logger.debug(
            f'"{command}": "{prefix}" {params}'
        )

        # TODO: Deferred threading
        handler(self, prefix, params)
