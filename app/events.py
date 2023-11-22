
from app.common.cache import leaderboards
from app.common.database.repositories import (
    infringements,
    clients,
    scores,
    stats,
    users
)

from datetime import datetime
from typing import Optional

import config
import json
import app

@app.session.events.register('user_update')
def user_update(user_id: int):
    if not (player := app.session.players.by_id(user_id)):
        return
    
    player.reload_object()

    for player in app.session.players:
        if player.client.version.date <= 377:
            player.enqueue_presence(player, update=True)
            continue

        player.enqueue_stats(player)

@app.session.events.register('bot_message')
def bot_message(message: str, target: str):
    if not (channel := app.session.channels.by_name(target)):
        return

    messages = message.split('\n')

    for message in messages:
        channel.send_message(
            app.session.bot_player,
            message,
            ignore_privs=True
        )

@app.session.events.register('restrict')
def restrict(
    user_id: int,
    reason: str = '',
    autoban: bool = False,
    until: Optional[datetime] = None
) -> None:
    if not (player := app.session.players.by_id(user_id)):
        # Player is not online
        player = users.fetch_by_id(user_id)

        if not player:
            # Player was not found
            return

        # Update user
        users.update(player.id,
            {
                'restricted': True,
                'permissions': 0
            }
        )

        leaderboards.remove(
            player.id,
            player.country
        )

        stats.delete_all(player.id)
        scores.hide_all(player.id)

        # Update hardware
        clients.update_all(player.id, {'banned': True})

        # Add entry inside infringements table
        infringements.create(
            player.id,
            action=0,
            length=until,
            description=reason,
            is_permanent=True if not until else False
        )

        app.session.logger.warning(
            f'{player.name} got {"auto-" if autoban else ""}restricted. Reason: {reason}'
        )
        return

    player.restrict(reason, until, autoban)

@app.session.events.register('silence')
def silence(user_id: int, duration: int, reason: str = ''):
    if not (player := app.session.players.by_id(user_id)):
        return

    player.silence(duration, reason)

@app.session.events.register('announcement')
def announcement(message: str):
    app.session.logger.info(f'Announcement: "{message}"')
    app.session.players.announce(message)

@app.session.events.register('osu_error')
def osu_error(user_id: int, error: dict):
    if not (player := app.session.players.by_id(user_id)):
        return

    app.session.logger.warning(
        f'Client error from "{player.name}":\n'
        f'{json.dumps(error, indent=4)}'
    )

    if channel := app.session.channels.by_name('#admin'):
        channel.send_message(
            app.session.bot_player,
            f'Client error from "{player.name}". Please check the logs!',
            ignore_privs=True
        )

    # When a beatmap fails to load inside a match, the player
    # gets forced to the menu screen. In this state, everything
    # is a little buggy, but aborting the match fixes pretty much everything.
    if player.match and player.match.in_progress:
        if not player.match.in_progress:
            return

        player.match.abort()
        player.match.chat.send_message(
            app.session.bot_player,
            f"Match was aborted, due to client error from {player.name}. "
            "Please try again!",
            ignore_privs=True
        )

@app.session.events.register('shutdown')
def shutdown():
    """Used to shutdown the event_listener thread"""
    exit()
