import logging


# Default format for all logs
log_format = '[%(asctime)s]  %(name)16s %(levelname)8s - %(message)s'

# Common logging config
logging.basicConfig(format=log_format)
logger = logging.getLogger('lone')


def log_init(level=logging.INFO):
    logger.setLevel(level)
    return logger


def log_get(level=logging.INFO):
    return logger
