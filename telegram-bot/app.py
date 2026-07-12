from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import settings
from access_middleware import AccessMiddleware
from handlers.language import router as language_router
from handlers.search import router as search_router
from handlers.start import router as start_router
from handlers.station import router as station_router
from handlers.operations import router as operations_router
from i18n import MENU, t
from keyboards import main_keyboard


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

fallback_router = Router()


@fallback_router.message(
    lambda message: message.text in {
        label
        for menu in MENU.values()
        for key, label in menu.items()
        if key not in {"new_station", "search_station"}
    }
)
async def menu_placeholder(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "tj")
    await message.answer(t(lang, "not_implemented"), reply_markup=main_keyboard(lang))


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.outer_middleware(AccessMiddleware())
    dp.include_router(start_router)
    dp.include_router(language_router)
    dp.include_router(station_router)
    dp.include_router(operations_router)
    dp.include_router(search_router)
    dp.include_router(fallback_router)
    return dp


async def main() -> None:
    settings.validate()
    bot = Bot(token=settings.bot_token)
    dp = build_dispatcher()
    logger.info("City Skyline Telegram bot starting")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
