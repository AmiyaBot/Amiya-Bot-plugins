from datetime import datetime

from amiyabot.database import *
from core.database.bot import BotBaseModel


@table
class ChannelRecord(BotBaseModel):
    channel_id: str = CharField()
    last_message: datetime = DateTimeField(null=True)
