"""Persistent newcomer activity deadline."""

from datetime import UTC, datetime

import ormar

from db.database import ormar_config


class PendingNewcomer(ormar.Model):
    ormar_config = ormar_config.copy(
        tablename="pending_newcomers",
        constraints=[ormar.UniqueColumns("chat_id", "user_id")],
    )

    id: int = ormar.Integer(primary_key=True, autoincrement=True)
    chat_id: int = ormar.BigInteger(index=True)
    user_id: int = ormar.BigInteger(index=True)
    deadline_at: datetime = ormar.DateTime(index=True)
    status: str = ormar.String(max_length=16, default="pending", index=True)
    created_at: datetime = ormar.DateTime(default=lambda: datetime.now(UTC).replace(tzinfo=None))
