
from app.common.streams import StreamIn

from .. import register_decoder
from . import RequestPacket
from . import Reader

from typing import Callable

def register(packet: RequestPacket) -> Callable:
    def wrapper(func) -> Callable:
        register_decoder(535, packet, func)
        register_decoder(504, packet, func)
        return func

    return wrapper

@register(RequestPacket.CREATE_MATCH)
def create_match(stream: StreamIn):
    return Reader(stream).read_match()

@register(RequestPacket.MATCH_CHANGE_SETTINGS)
def change_settings(stream: StreamIn):
    return Reader(stream).read_match()

@register(RequestPacket.MATCH_CHANGE_PASSWORD)
def change_password(stream: StreamIn):
    return Reader(stream).read_match().password

@register(RequestPacket.BEATMAP_INFO)
def beatmap_info(stream: StreamIn):
    return Reader(stream).read_beatmap_request()

@register(RequestPacket.MATCH_SCORE_UPDATE)
def score_update(stream: StreamIn):
    return Reader(stream).read_scoreframe()
