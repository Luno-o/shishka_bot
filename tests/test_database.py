from sqlalchemy import create_engine, inspect, text

from db.database import _add_missing_columns


def test_legacy_schema_is_migrated_without_data_loss(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE cat_photos ("
                "id INTEGER PRIMARY KEY, file_id TEXT NOT NULL, "
                "file_unique_id TEXT NOT NULL UNIQUE, added_by INTEGER NOT NULL, "
                "added_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO cat_photos "
                "(id, file_id, file_unique_id, added_by, added_at) "
                "VALUES (1, 'file', 'unique', 42, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE members ("
                "id INTEGER PRIMARY KEY, user_id BIGINT UNIQUE, "
                "messages_count INTEGER DEFAULT 0, reputation_points INTEGER DEFAULT 0, "
                "violations_count_profanity INTEGER DEFAULT 0, "
                "violations_count_spam INTEGER DEFAULT 0)"
            )
        )
        connection.execute(text("CREATE TABLE spam (id INTEGER PRIMARY KEY, message TEXT UNIQUE, is_spam BOOLEAN)"))

        _add_missing_columns(connection)
        _add_missing_columns(connection)

        assert connection.execute(text("SELECT COUNT(*) FROM cat_photos")).scalar_one() == 1
        assert connection.execute(text("SELECT media_type FROM cat_photos WHERE id = 1")).scalar_one() == "photo"

        inspector = inspect(connection)
        assert {"description", "media_type"} <= {column["name"] for column in inspector.get_columns("cat_photos")}
        assert {"date", "halloween_sweets", "halloween_golden_tickets"} <= {
            column["name"] for column in inspector.get_columns("members")
        }
        assert {"is_blocked", "date", "chat_id", "user_id"} <= {
            column["name"] for column in inspector.get_columns("spam")
        }
