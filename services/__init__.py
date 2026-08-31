import sys

# ensure libs are importable (censure, gender_extractor)
if "./libs" not in sys.path:
    sys.path.insert(0, "./libs")

from .gender import Gender, detect_gender
from .cache import (
    retrieve_or_create_member,
    retrieve_tgmember,
    detect_gender as detect_gender_cached,
    invalidate_member_cache,
    invalidate_tgmember_cache,
)

__all__ = [
    "Gender",
    "detect_gender",
    "detect_gender_cached",
    "retrieve_or_create_member",
    "retrieve_tgmember",
    "invalidate_member_cache",
    "invalidate_tgmember_cache",
]
