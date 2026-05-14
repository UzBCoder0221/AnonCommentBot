from aiogram import Router

from filters import ChatPrivateFilter
from aiogram.client.session.middlewares.request_logging import logger


def setup_routers() -> Router:
    # from .users import admin, start, help, echo
    # from .errors import error_handler
    from .groups import smth
    router = Router()

    # Agar kerak bo'lsa, o'z filteringizni o'rnating
    # start.router.message.filter(ChatPrivateFilter(chat_type=["private"]))

    # router.include_routers(admin.router, start.router, smth.router, help.router, echo.router, error_handler.router)
    router.include_routers(smth.router)

    return router
