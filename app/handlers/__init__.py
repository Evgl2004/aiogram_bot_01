"""
Пакет обработчиков (handlers).
Содержит функцию для подключения всех роутеров к диспетчеру.
"""

from aiogram import Dispatcher

# Импортируем роутеры из соответствующих модулей
# Обработчик команды /start
from .start import router as start_router
# Обработчики /help и /status
from .help import router as help_router
# Обработчики административные (команда /admin, рассылки)
from .admin import combined_router as admin_router
# Обработчик процесса регистрации
from .registration import router as registration_router
# Обработчик главного меню и подменю
from .menu import router as menu_router
# Маршрутизатор для обновления устаревших пользователей.
from .legacy import router as legacy_router


def setup_routers(dp: Dispatcher) -> None:
    """
    Подключает все роутеры к диспетчеру.
    Вызывается при запуске бота (в main.py).

    Args:
        dp (Dispatcher): экземпляр диспетчера Aiogram
    """

    # Подключаем админский роутер (он может включать в себя несколько подроутеров)
    dp.include_router(admin_router)

    # Подключаем роутер команды /start
    dp.include_router(start_router)

    # Подключаем роутер справки (/help, /status)
    dp.include_router(help_router)

    # Подключаем роутер регистрации (обработчики согласий, контакта, анкеты)
    dp.include_router(registration_router)

    # Подключаем роутер главного меню и подменю
    dp.include_router(menu_router)

    # Подключаем роутер для обновления устаревших пользователей.
    dp.include_router(legacy_router)
