from datetime import datetime

from peewee import AutoField,CharField,TextField,DateTimeField

from amiyabot.database import ModelClass

from core.database.plugin import db

class AmiyaBotFunctionsGroupDataBase(ModelClass):
    id: int = AutoField()
    channel_id: str = CharField()
    last_message: datetime = DateTimeField(null=True)

    class Meta:
        database = db
        table_name = "amiyabot-functions-group"