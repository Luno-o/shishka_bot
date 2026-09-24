"""
Admin action handlers (ban, unban, etc.).
"""
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatPermissions, Message

from config import config
from db.models import Member
from filters import MemberCanRestrictFilter, InMainGroups, IsOwnerFilter
from services.audit_log import get_recent
from services.cache import get_member_orm, update_member_cache
from services.ephemeral import cleanup_trigger, make_ephemeral
from services.moderation_policy import add_allowed_domain, get_effective_allowlist, remove_allowed_domain
from services.raid_guard import clear_raid, is_raid_active
from services.metrics import increment as record_metric
from services.warn_service import add_warning, clear_warnings, consequence_for, count_warnings, remove_latest_warning
from utils import get_string, MemberStatus, user_mention_by_id

router = Router(name="admin_actions")


_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


@router.message(
    InMainGroups(),
    Command("top", "топ", prefix="!/")
)
async def cmd_top(message: Message, command: CommandObject) -> None:
    """
    Show the reputation leaderboard for this chat's members (everyone).

    Usage: !top [count]  (default 10, max 25)
    """
    count = _parse_count(command, default=10, max_val=25)

    top_members = await Member.objects.order_by("-reputation_points").limit(count).all()

    if not top_members:
        await message.reply("🏆 Пока нет данных для топа.")
        return

    lines = [f"🏆 <b>Топ-{len(top_members)} по репутации:</b>\n"]
    for i, member in enumerate(top_members, 1):
        prefix = _MEDALS.get(i, f"{i}.")
        lines.append(f"{prefix} {user_mention_by_id(member.user_id)} — <b>{member.reputation_points}</b>")

    sent = await message.reply("\n".join(lines))
    make_ephemeral(message, sent, config.ephemeral.stats_ttl)
    await cleanup_trigger(message)


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("ban", prefix="!/")
)
async def cmd_ban(message: Message) -> None:
    """Ban a user (reply to their message)."""
    if not message.reply_to_message:
        await message.reply(get_string("error_no_reply"))
        return

    # admins cannot be banned
    user = await message.bot.get_chat_member(
        message.chat.id,
        message.reply_to_message.from_user.id
    )
    if user.status in MemberStatus.admin_statuses():
        await message.reply(get_string("error_ban_admin"))
        return

    # remove admin's command
    await message.delete()

    # ban
    await message.bot.ban_chat_member(
        chat_id=message.chat.id,
        user_id=message.reply_to_message.from_user.id
    )

    await message.reply_to_message.reply(get_string("resolved_ban"))


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("unban", prefix="!/")
)
async def cmd_unban(message: Message) -> None:
    """Unban a user (reply to their message)."""
    if not message.reply_to_message:
        await message.reply(get_string("error_no_reply"))
        return

    # admins cannot be unbanned
    user = await message.bot.get_chat_member(
        message.chat.id,
        message.reply_to_message.from_user.id
    )
    if user.status in MemberStatus.admin_statuses():
        await message.reply(get_string("error_ban_admin"))
        return

    # remove admin's command
    await message.delete()

    # unban
    await message.bot.unban_chat_member(
        chat_id=message.chat.id,
        user_id=message.reply_to_message.from_user.id
    )

    await message.reply_to_message.reply(get_string("resolved_unban"))


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("raid_off", "антирейд_выкл", prefix="!/")
)
async def cmd_raid_off(message: Message) -> None:
    """Manually lift raid-mode restrictions for this chat (admin only)."""
    if not is_raid_active(message.chat.id):
        await message.reply("🛡️ Режим антирейда сейчас не активен в этом чате.")
        return

    clear_raid(message.chat.id)
    await message.reply(
        "🛡️ Режим антирейда отключён. "
        "Новые участники больше не будут автоматически ограничиваться."
    )


_CONSEQUENCE_LABELS = {
    "mute_1h": "🔇 мут на 1 час",
    "mute_1d": "🔇 мут на 1 день",
    "ban": "🚫 бан",
}


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("warn", "варн", "предупреждение", prefix="!/")
)
async def cmd_warn(message: Message, command: CommandObject) -> None:
    """
    Issue a formal warning (reply to the offending message, admin only).

    Warnings accumulate per chat; at configured counts they escalate
    automatically to a mute and finally a ban (see [warn] in config.toml).

    Usage: !warn [причина]
    """
    if not message.reply_to_message:
        await message.reply(get_string("error_no_reply"))
        return

    target = message.reply_to_message.from_user
    target_member = await message.bot.get_chat_member(message.chat.id, target.id)
    if target_member.status in MemberStatus.admin_statuses():
        await message.reply(get_string("error_ban_admin"))
        return

    reason = command.args.strip() if command.args else None

    new_count = await add_warning(message.chat.id, target.id, message.from_user.id, reason)
    record_metric("warnings_issued")
    consequence = consequence_for(new_count)

    text = f"⚠️ {user_mention_by_id(target.id)} получает предупреждение ({new_count})."
    if reason:
        text += f"\n<i>Причина:</i> {reason}"

    if consequence == "mute_1h":
        until = datetime.now(timezone.utc) + timedelta(hours=1)
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id, user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until,
        )
        text += f"\n{_CONSEQUENCE_LABELS[consequence]} (порог: {config.warn.mute_1h_at} предупреждений)"
    elif consequence == "mute_1d":
        until = datetime.now(timezone.utc) + timedelta(days=1)
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id, user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until,
        )
        text += f"\n{_CONSEQUENCE_LABELS[consequence]} (порог: {config.warn.mute_1d_at} предупреждений)"
    elif consequence == "ban":
        await message.bot.ban_chat_member(chat_id=message.chat.id, user_id=target.id)
        text += f"\n{_CONSEQUENCE_LABELS[consequence]} (порог: {config.warn.ban_at} предупреждений)"

    await message.reply(text)


@router.message(
    InMainGroups(),
    Command("warns", "варны", prefix="!/")
)
async def cmd_warns(message: Message) -> None:
    """Check a user's warning count (reply to check someone else; no reply = yourself)."""
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user

    count = await count_warnings(message.chat.id, target.id)
    await message.reply(f"⚠️ {user_mention_by_id(target.id)}: <b>{count}</b> предупреждени(й/е) в этом чате.")


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("unwarn", prefix="!/")
)
async def cmd_unwarn(message: Message) -> None:
    """Remove a user's most recent warning (reply to their message, admin only)."""
    if not message.reply_to_message:
        await message.reply(get_string("error_no_reply"))
        return

    target = message.reply_to_message.from_user
    removed = await remove_latest_warning(message.chat.id, target.id)
    if removed:
        remaining = await count_warnings(message.chat.id, target.id)
        await message.reply(f"✅ Последнее предупреждение снято. Осталось: {remaining}.")
    else:
        await message.reply(f"У {user_mention_by_id(target.id)} нет предупреждений в этом чате.")


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("clearwarns", prefix="!/")
)
async def cmd_clear_warns(message: Message) -> None:
    """Wipe all of a user's warnings in this chat (reply to their message, admin only)."""
    if not message.reply_to_message:
        await message.reply(get_string("error_no_reply"))
        return

    target = message.reply_to_message.from_user
    removed = await clear_warnings(message.chat.id, target.id)
    if removed:
        await message.reply(f"🧹 Все предупреждения {user_mention_by_id(target.id)} сброшены ({removed}).")
    else:
        await message.reply(f"У {user_mention_by_id(target.id)} и так нет предупреждений в этом чате.")


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("adminhelp", "хелп_админ", prefix="!/")
)
async def cmd_admin_help(message: Message) -> None:
    """List the moderation/admin commands in-chat (admin only) - the same
    set documented in README.md, kept here so admins don't need to go
    looking for the file."""
    text = (
        "🛡️ <b>Команды модерации</b>\n\n"
        "<b>Пользователи</b>\n"
        "!ban / !unban — забанить / разбанить (ответом на сообщение)\n"
        "!warn [причина] — выдать предупреждение (ответом); копится и эскалирует до мута/бана\n"
        "!warns — посмотреть предупреждения (ответом — чужие, без ответа — свои)\n"
        "!unwarn — снять последнее предупреждение (ответом)\n"
        "!clearwarns — сбросить все предупреждения (ответом)\n"
        "!trust — быстрый фикс ложного срабатывания: поднять репутацию, сбросить спам-нарушения, снять мут (ответом)\n\n"
        "<b>Ссылки</b>\n"
        "!linkallow [домен] — добавить домен в белый список; без аргумента — показать список\n"
        "!linkdeny домен — убрать домен из белого списка\n\n"
        "<b>Антирейд</b>\n"
        "!raid_off — снять режим антирейда в этом чате\n\n"
        "<b>Диагностика</b>\n"
        "!falsepositives [N] — последние автоудаления модерацией в этом чате\n\n"
        "<i>Только для владельца бота:</i>\n"
        "!backup_now, !metrics, !reload, !top_violators_spam [N], !top_violators_profanity [N], "
        "!msg, !log, !chatid"
    )
    await message.reply(text)


def _parse_count(command: CommandObject, default: int = 10, max_val: int = 50) -> int:
    """Parse count argument from command, with bounds."""
    if not command.args:
        return default
    try:
        count = int(command.args.strip())
        return max(1, min(count, max_val))
    except ValueError:
        return default


@router.message(
    IsOwnerFilter(),
    Command("top_violators_profanity", prefix="!/")
)
async def cmd_top_violators_profanity(message: Message, command: CommandObject) -> None:
    """
    Show top profanity violators (owner only, works in PM and groups).
    
    Usage: /top_violators_profanity [count]
    Default count: 10, Max: 50
    """
    count = _parse_count(command)
    
    # query db
    violators = await Member.objects.filter(
        violations_count_profanity__gt=0
    ).order_by("-violations_count_profanity").limit(count).all()
    
    if not violators:
        await message.reply("🧼 Нарушителей не найдено")
        return
    
    # build response
    lines = [f"🤬 <b>Топ-{len(violators)} нарушителей (мат):</b>\n"]
    
    for i, member in enumerate(violators, 1):
        lines.append(
            f"{i}. {user_mention_by_id(member.user_id)} — "
            f"<b>{member.violations_count_profanity}</b> нарушений"
        )
    
    await message.reply("\n".join(lines))


@router.message(
    IsOwnerFilter(),
    Command("top_violators_spam", prefix="!/")
)
async def cmd_top_violators_spam(message: Message, command: CommandObject) -> None:
    """
    Show top spam violators (owner only, works in PM and groups).
    
    Usage: /top_violators_spam [count]
    Default count: 10, Max: 50
    """
    count = _parse_count(command)
    
    # query db
    violators = await Member.objects.filter(
        violations_count_spam__gt=0
    ).order_by("-violations_count_spam").limit(count).all()
    
    if not violators:
        await message.reply("🧼 Нарушителей не найдено")
        return
    
    # build response
    lines = [f"📨 <b>Топ-{len(violators)} нарушителей (спам):</b>\n"]
    
    for i, member in enumerate(violators, 1):
        lines.append(
            f"{i}. {user_mention_by_id(member.user_id)} — "
            f"<b>{member.violations_count_spam}</b> нарушений"
        )

    await message.reply("\n".join(lines))


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("trust", "доверие", prefix="!/")
)
async def cmd_trust(message: Message) -> None:
    """
    Quick manual fix for a false positive (reply to the user's message,
    admin only): raises their reputation just above the exemption
    threshold, clears their spam-violation count, and lifts any active
    mute in this chat. Doesn't touch !warn warnings - use !unwarn/!clearwarns
    for those.
    """
    if not message.reply_to_message:
        await message.reply(get_string("error_no_reply"))
        return

    target = message.reply_to_message.from_user

    member = await get_member_orm(target.id)
    new_reputation = max(member.reputation_points, config.spam.exempt_reputation_threshold + 1)
    await member.update(reputation_points=new_reputation, violations_count_spam=0)
    update_member_cache(target.id, member)

    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=True),
        )
    except Exception:
        pass  # user wasn't restricted, or bot lacks rights - either way, not fatal

    await message.reply(
        f"✅ {user_mention_by_id(target.id)} помечен как доверенный: "
        f"репутация поднята до <b>{new_reputation}</b>, счётчик спам-нарушений сброшен, "
        f"мут (если был) снят."
    )


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("linkallow", prefix="!/")
)
async def cmd_linkallow(message: Message, command: CommandObject) -> None:
    """
    Add a domain to the link allowlist without touching config.toml or
    restarting the bot (admin only). No argument -> show the current list.

    Usage: !linkallow example.com
    """
    if not command.args:
        domains = sorted(get_effective_allowlist())
        text = "🔗 <b>Разрешённые домены:</b>\n" + (", ".join(domains) if domains else "список пуст.")
        await message.reply(text)
        return

    domain = command.args.strip()
    try:
        added = await add_allowed_domain(domain, message.from_user.id)
    except ValueError:
        await message.reply("❌ Похоже на некорректный домен. Пример: <code>!linkallow example.com</code>")
        return

    if added:
        await message.reply(f"✅ Домен <code>{domain}</code> добавлен в белый список ссылок.")
    else:
        await message.reply(f"ℹ️ Домен <code>{domain}</code> уже в белом списке.")


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("linkdeny", prefix="!/")
)
async def cmd_linkdeny(message: Message, command: CommandObject) -> None:
    """
    Remove a chat-added domain from the link allowlist (admin only).

    Usage: !linkdeny example.com
    """
    if not command.args:
        await message.reply("Использование: <code>!linkdeny example.com</code>")
        return

    domain = command.args.strip()
    result = await remove_allowed_domain(domain)

    if result is True:
        await message.reply(f"✅ Домен <code>{domain}</code> убран из белого списка.")
    elif result is None:
        await message.reply(
            f"⚠️ Домен <code>{domain}</code> задан в config.toml ([spam].link_domain_allowlist) - "
            f"из чата его не убрать, нужно поправить файл и перезапустить бота."
        )
    else:
        await message.reply(f"ℹ️ Домена <code>{domain}</code> и так нет в белом списке.")


@router.message(
    InMainGroups(),
    MemberCanRestrictFilter(),
    Command("falsepositives", "лп", prefix="!/")
)
async def cmd_false_positives(message: Message, command: CommandObject) -> None:
    """
    Show the last few messages auto-deleted by moderation in this chat, so
    admins can spot false positives without digging through the logs
    channel (admin only).

    Usage: !falsepositives [count]  (default 10, max 30)
    """
    count = _parse_count(command, default=10, max_val=30)
    entries = get_recent(message.chat.id, limit=count)

    if not entries:
        await message.reply("🕵️ Пока нет недавних автоудалений в этом чате.")
        return

    lines = [f"🕵️ <b>Последние {len(entries)} автоудалений в этом чате:</b>\n"]
    for entry in entries:
        stamp = entry.at.strftime("%d.%m %H:%M")
        lines.append(
            f"• {stamp} — <i>{entry.reason}</i> — {user_mention_by_id(entry.user_id)}: "
            f"«{entry.snippet}»"
        )

    await message.reply("\n".join(lines))
