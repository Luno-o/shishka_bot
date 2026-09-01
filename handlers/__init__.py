"""
Handler registration for the bot.
"""

from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher) -> None:
    """Register all routers with the dispatcher."""
    # Keep imports lazy: CLI utilities and focused tests should not load ML models.
    from . import (
        admin_actions,
        callbacks,
        exceptions,
        group_events,
        help,
        personal_actions,
        shish_tarot,
        user_actions,
    )
    from .cat_commands import router as cat_commands_router

    # Error handler should be first
    dp.include_router(exceptions.router)

    # Admin actions
    dp.include_router(admin_actions.router)

    # User actions (report, @admin)
    dp.include_router(user_actions.router)

    # Callback handlers
    dp.include_router(callbacks.router)

    # Personal/owner actions (ping, profanity check)
    dp.include_router(personal_actions.router)

    # Public utility and entertainment commands must precede catch-all moderation.
    dp.include_router(help.router)
    dp.include_router(shish_tarot.router)
    dp.include_router(cat_commands_router)

    # Group events (main message processing) - should be last
    dp.include_router(group_events.router)


__all__ = ["register_all_handlers"]
