from services import audit_log


def test_record_and_get_recent_for_chat():
    audit_log.reset()
    audit_log.record_deletion(chat_id=1, user_id=100, reason="ссылка", text="buy now http://spam.example")
    audit_log.record_deletion(chat_id=1, user_id=101, reason="CN-спам", text="举报垃圾邮件")
    audit_log.record_deletion(chat_id=2, user_id=200, reason="ссылка", text="unrelated chat")

    entries = audit_log.get_recent(chat_id=1)
    assert len(entries) == 2
    # newest first
    assert entries[0].reason == "CN-спам"
    assert entries[1].reason == "ссылка"
    assert all(entry.chat_id == 1 for entry in entries)


def test_get_recent_respects_limit():
    audit_log.reset()
    for i in range(5):
        audit_log.record_deletion(chat_id=1, user_id=i, reason="ссылка", text=f"msg {i}")

    entries = audit_log.get_recent(chat_id=1, limit=2)
    assert len(entries) == 2
    # newest first: msg 4, then msg 3
    assert entries[0].snippet == "msg 4"
    assert entries[1].snippet == "msg 3"


def test_snippet_truncation_and_empty_text():
    audit_log.reset()
    long_text = "a" * 300
    audit_log.record_deletion(chat_id=1, user_id=1, reason="ссылка", text=long_text)
    audit_log.record_deletion(chat_id=1, user_id=2, reason="NSFW", text=None)

    entries = audit_log.get_recent(chat_id=1)
    assert entries[0].snippet == "[без текста]"
    assert len(entries[1].snippet) <= audit_log._SNIPPET_LIMIT
    assert entries[1].snippet.endswith("…")


def test_deque_respects_max_entries():
    audit_log.reset()
    for i in range(audit_log.MAX_ENTRIES + 10):
        audit_log.record_deletion(chat_id=1, user_id=i, reason="ссылка", text=str(i))

    assert len(audit_log._log) == audit_log.MAX_ENTRIES
    # oldest entries were dropped, most recent ones survive
    entries = audit_log.get_recent(chat_id=1, limit=audit_log.MAX_ENTRIES)
    assert entries[0].snippet == str(audit_log.MAX_ENTRIES + 9)
