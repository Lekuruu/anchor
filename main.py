
from twisted.internet import reactor

from app.common.logging import Console, File
from app.irc.server import IRCFactory
from app.server import BanchoFactory

import logging
import config
import utils
import app

logging.basicConfig(
    handlers=[Console, File],
    level=logging.DEBUG
        if config.DEBUG
        else logging.INFO
)

def main():
    utils.setup()

    bancho = BanchoFactory()
    irc = IRCFactory()

    for port in config.PORTS:
        reactor.listenTCP(port, bancho)
        app.session.logger.info(
            f'Reactor listening on port: {port}'
        )

    reactor.listenTCP(config.IRC_PORT, irc)
    app.session.logger.info(
        f'Reactor listening on port: {config.IRC_PORT}'
    )

    reactor.run()

if __name__ == "__main__":
    main()
