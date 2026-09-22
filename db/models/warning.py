"""Formal moderation warnings (the !warn escalation ladder)."""

from datetime import datetime

import ormar

from db.database import ormar_config


class Warning(ormar.Model):
    ormar_config = ormar_config.copy(tablename="warnings")

    id: int = ormar.Integer(primary_key=True, autoincrement=True)
    chat_id: int = ormar.BigInteger(index=True)
    user_id: int = ormar.BigInteger(index=True)
    admin_id: int = ormar.BigInteger()
    reason: str = ormar.String(max_length=500, nullable=True)
    date: datetime = ormar.DateTime(default=datetime.now)
