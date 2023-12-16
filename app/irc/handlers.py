
from __future__ import annotations
from typing import Dict, Callable

from .client import IRCClient

HANDLERS: Dict[str, Callable] = {}

def register(command: str) -> Callable:
    """Register a command handler"""
    def wrapper(func: Callable):
        HANDLERS[command] = func
        return func
    return wrapper

@register('USER')
def user_handler(client: IRCClient, prefix, params):
    ...

@register('PASS')
def pass_handler(client: IRCClient, prefix, params):
    ...

@register('NICK')
def nick_handler(client: IRCClient, prefix, params):
    ...

@register('QUIT')
def quit_handler(client: IRCClient, prefix, params):
    ...

@register('JOIN')
def join_handler(client: IRCClient, prefix, params):
    ...

@register('PART')
def part_handler(client: IRCClient, prefix, params):
    ...

@register('TOPIC')
def topic_handler(client: IRCClient, prefix, params):
    ...

@register('PRIVMSG')
def pm_handler(client: IRCClient, prefix, params):
    ...

@register('MOTD')
def motd_handler(client: IRCClient, prefix, params):
    ...

@register('LUSERS')
def lusers_handler(client: IRCClient, prefix, params):
    ...

@register('PING')
def ping_handler(client: IRCClient, prefix, params):
    ...

@register('PONG')
def pong_handler(client: IRCClient, prefix, params):
    ...

@register('AWAY')
def away_handler(client: IRCClient, prefix, params):
    ...

@register('WHO')
def who_handler(client: IRCClient, prefix, params):
    ...

@register('WHOIS')
def whois_handler(client: IRCClient, prefix, params):
    ...

@register('MODE')
def mode_handler(client: IRCClient, prefix, params):
    ...
