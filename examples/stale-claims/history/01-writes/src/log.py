import logging


def debug(message):
    logging.getLogger("store").debug(message)
