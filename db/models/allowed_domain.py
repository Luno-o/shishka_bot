"""
Chat-added entries for the link allowlist (see services/moderation_policy.py
and the !linkallow / !linkdeny commands in handlers/admin_actions.py).

Kept separate from config.toml's static [spam].link_domain_allowlist so
admins can add/remove domains from chat without editing the file or
restarting the bot. Persisted (not just in-memory) so the additions survive
a restart too.
"""
from datetime import datetime

import ormar

from db.database import ormar_config


class AllowedDomain(ormar.Model):
    ormar_config = ormar_config.copy(tablename="allowed_domains")

    id: int = ormar.Integer(primary_key=True, autoincrement=True)
    domain: str = ormar.String(max_length=255, unique=True)
    added_by: int = ormar.BigInteger()
    added_at: datetime = ormar.DateTime(default=datetime.now)
