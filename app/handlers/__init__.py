"""
Пакет обработчиков (handlers) приложения.

Этот файл объединяет все хендлеры бота и предоставляет функцию setup_routers
для их регистрации в диспетчере.
"""

from aiogram import Dispatcher

# Импортируем роутеры из всех модулей
from .start import router as start_router
from .help import router as help_router
from .registration import router as registration_router
from .menu import router as menu_router
from .legacy import router as legacy_router
from .admin import combined_router as admin_router
from .moderation import router as moderation_router


def setup_routers(dp: Dispatcher) -> None:
    """
    Регистрация всех роутеров в диспетчере.

    Args:
        dp (Dispatcher): Диспетчер бота для регистрации роутеров
    """
    # Регистрируем роутеры в порядке приоритета
    dp.include_router(start_router)           # Роутер команды /start
    dp.include_router(help_router)              # Роутер команды /help
    dp.include_router(registration_router)      # Роутер регистрации
    dp.include_router(menu_router)              # Роутер главного меню
    dp.include_router(legacy_router)            # Роутер апгрейда устаревших пользователей
    dp.include_router(admin_router)             # Роутер команд администратора
    dp.include_router(moderation_router)        # Роутер модерации
