from datetime import datetime

from peewee import AutoField,CharField,IntegerField,DateTimeField,TextField

from amiyabot.database import ModelClass

from core.database.plugin import db

class AmiyaBotBLMLibraryTokenConsumeModel(ModelClass):
    id: int = AutoField()
    exec_id = CharField()
    channel_id = CharField(null=True)
    model_name = CharField()
    prompt_tokens = IntegerField()
    completion_tokens = IntegerField()
    total_tokens = IntegerField()
    exec_time = DateTimeField()

    class Meta:
        database = db
        table_name = "amiyabot-blm-library-token-consume"

class AmiyaBotBLMLibraryMetaStorageModel(ModelClass):
    id: int = AutoField()
    key = CharField()
    meta_str = TextField()

    class Meta:
        database = db
        table_name = "amiyabot-blm-library-meta-storage"