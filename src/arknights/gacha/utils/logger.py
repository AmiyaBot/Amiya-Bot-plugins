from amiyabot.log import LoggerManager

logger = LoggerManager('Gacha')


def debug_log(message):
    logger.info(f'{message}')
