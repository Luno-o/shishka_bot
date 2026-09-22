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
from services.ephemeral import cleanup_trigger, make_ephemeral
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
