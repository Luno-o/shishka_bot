"""Persistent daily Shish-tarot assignment."""

from datetime import datetime

import ormar

from db.database import ormar_config


class ShishTarotReading(ormar.Model):
    ormar_config = ormar_config.copy(
        tablename="shish_tarot_readings",
        constraints=[ormar.UniqueColumns("user_id", "reading_date")],
    )

    id: int = ormar.Integer(primary_key=True, autoincrement=True)
    user_id: int = ormar.BigInteger(index=True)
    reading_date: str = ormar.String(max_length=10, index=True)
    cat_photo_id: int = ormar.Integer()
    created_at: datetime = ormar.DateTime(default=datetime.now)
