from datetime import datetime

import ormar

from db.database import ormar_config


class CatPhoto(ormar.Model):
    ormar_config = ormar_config.copy(tablename="cat_photos")

    id: int = ormar.Integer(primary_key=True, autoincrement=True)
    file_id: str = ormar.String(max_length=255)
    file_unique_id: str = ormar.String(max_length=255, unique=True)
    added_by: int = ormar.BigInteger()
    added_at: datetime = ormar.DateTime(default=datetime.now)
    description: str = ormar.String(max_length=500, nullable=True)