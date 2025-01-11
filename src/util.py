from http.client import HTTPResponse
import os
from typing import Awaitable, Callable, Optional
import logging as log

MessageSender = Callable[
    [int, str, str, Optional[list[tuple[HTTPResponse, str]]]], Awaitable[None]
]


def make_dir_if_not_exist(path):
    if not os.path.exists(path):
        log.debug(f"creates dir {path}")
        os.makedirs(path)
