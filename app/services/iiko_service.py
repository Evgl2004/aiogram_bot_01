"""
Асинхронный сервис для работы с iiko API.
"""

from typing import Optional, Dict, Any, Tuple, List

from app.services.iiko_async import AsyncIikoApi
from app.config import settings
from loguru import logger

# Глобальный экземпляр асинхронного клиента
_iiko_client: Optional[AsyncIikoApi] = None


async def init_iiko_client():
    """Инициализирует клиент iiko. Должен быть вызван при старте бота."""
    global _iiko_client
    _iiko_client = AsyncIikoApi(api_key=settings.IIKO_API_KEY, organization_id=settings.DEFAULT_ORG_ID)
    logger.info("iiko async client initialized")


async def close_iiko_client():
    """Закрывает клиент iiko. Должен быть вызван при остановке бота."""
    global _iiko_client
    if _iiko_client:
        await _iiko_client.close()
        _iiko_client = None
        logger.info("iiko async client closed")


def _get_client() -> AsyncIikoApi:
    """Возвращает экземпляр клиента (должен быть инициализирован ранее)."""
    if _iiko_client is None:
        raise RuntimeError("iiko client not initialized. Call init_iiko_client() first.")
    return _iiko_client


async def get_customer_info(phone: str) -> Optional[Dict[str, Any]]:
    """Получает информацию о клиенте из iiko."""
    return await _get_client().get_customer_info(phone)


async def register_customer(user) -> Tuple[Optional[str], str]:
    """
    Регистрирует клиента в iiko, используя все доступные данные из анкеты.
    """

    # Преобразуем пол в формат iiko (1 - male, 2 - female)
    sex_map = {"male": 1, "female": 2}
    sex = sex_map.get(user.gender) if user.gender else None

    # Форматируем дату рождения
    birth_date_str = user.birth_date.strftime("%Y-%m-%d") if user.birth_date else None

    return await _get_client().register_customer(
        phone=user.phone_number,
        name=user.first_name_input or "",
        surname=user.last_name_input or "",
        birth_date=birth_date_str,
        sex=sex,
        email=user.email or "",
        should_receive_promo=user.notifications_allowed,
        should_receive_loyalty=user.notifications_allowed
    )


async def add_card(customer_id: str, card_number: str) -> Tuple[bool, str]:
    """Добавляет карту клиенту."""
    return await _get_client().add_card(customer_id, card_number)


async def get_loyalty_programs() -> List[Dict[str, Any]]:
    """Получает список программ лояльности."""
    return await _get_client().get_loyalty_programs()


async def add_customer_to_program(customer_id: str, program_id: Optional[str] = None) -> Tuple[bool, str]:
    """Подключает клиента к программе лояльности."""
    return await _get_client().add_customer_to_program(customer_id, program_id)


async def issue_card_for_customer(phone: str, customer_id: str) -> Tuple[bool, str, Optional[str]]:
    """
    Полный процесс выдачи карты клиенту.
    Возвращает (успех, сообщение, номер_карты).
    """

    from datetime import datetime

    # Создаём пустую строку, куда будем добавлять цифры
    phone_digits = ""

    # Перебираем каждый символ в исходной строке
    for character in phone:
        # Если символ – цифра, добавляем его к результату
        if character.isdigit():
            phone_digits += character

    card_number = f"{phone_digits}_{datetime.now().strftime('%Y%m%d')}"

    ok, msg = await add_card(customer_id, card_number)
    if not ok:
        return False, msg, None

    prog_ok, prog_msg = await add_customer_to_program(customer_id)
    if not prog_ok:
        logger.warning(f"Карта добавлена, но не подключена к программе: {prog_msg}")
        return True, f"✅ Карта {card_number} добавлена, но не подключена к программе", card_number

    return True, f"✅ Карта {card_number} успешно выпущена и подключена", card_number
