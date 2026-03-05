"""
Сервис синхронизации пользователя с iiko.
"""

from typing import Union

from aiogram import types
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.database import db
from app.database.models import User
from app.services import iiko_service
from app.keyboards.iiko import retry_keyboard
from app.utils.qr import generate_qr_code
from app.handlers.menu import show_main_menu


async def sync_user_with_iiko(
    obj: Union[types.CallbackQuery, types.Message],
    state: FSMContext,
    user: User
) -> None:
    """
    Синхронизирует данные пользователя с iiko.
    При успехе устанавливает is_registered=True и показывает главное меню.
    При ошибке предлагает повторить.
    """

    phone = user.phone_number
    if not phone:
        text = "❌ Ошибка: номер телефона не найден."
        if isinstance(obj, types.CallbackQuery):
            await obj.message.answer(text)
            await obj.answer()
        else:
            await obj.answer(text)
        await state.clear()
        return

    # 1. Пытаемся получить информацию о клиенте
    try:
        client_info = await iiko_service.get_customer_info(phone)
    except Exception as e:
        logger.error(f"Ошибка при запросе iiko для пользователя {user.id}: {e}")
        client_info = None

    # 2. Если клиент не найден – регистрируем нового
    if client_info is None:
        customer_id, reg_msg = await iiko_service.register_customer(user)
        if not customer_id:
            text = f"❌ Не удалось зарегистрировать в iiko.\nПричина: {reg_msg}"
            if isinstance(obj, types.CallbackQuery):
                await obj.message.edit_text(text, reply_markup=retry_keyboard())
                await obj.answer()
            else:
                await obj.answer(text, reply_markup=retry_keyboard())
            return
        # Клиент создан, карт пока нет
        client_info = {'customer_id': customer_id, 'cards': []}
    else:
        # 3. Клиент существует – обновляем его данные
        customer_id, upd_msg = await iiko_service.register_customer(user)  # create_or_update
        if not customer_id:
            text = f"❌ Не удалось обновить данные в iiko.\nПричина: {upd_msg}"
            if isinstance(obj, types.CallbackQuery):
                await obj.message.edit_text(text, reply_markup=retry_keyboard())
                await obj.answer()
            else:
                await obj.answer(text, reply_markup=retry_keyboard())
            return
        # Используем полученный customer_id
        client_info['customer_id'] = customer_id

    # 4. Проверяем наличие карт
    cards = client_info.get('cards', [])
    if not cards:
        # Выпускаем карту
        success, card_msg, card_number = await iiko_service.issue_card_for_customer(
            phone, client_info['customer_id'], user.first_name_input or ""
        )
        if not success:
            text = f"❌ Не удалось выпустить карту.\nПричина: {card_msg}"
            if isinstance(obj, types.CallbackQuery):
                await obj.message.edit_text(text, reply_markup=retry_keyboard())
                await obj.answer()
            else:
                await obj.answer(text, reply_markup=retry_keyboard())
            return
        # Обновляем список карт
        client_info = await iiko_service.get_customer_info(phone)
        if client_info:
            cards = client_info.get('cards', [])
        if not cards:
            cards = [{'number': card_number}]

    # 5. Успех – устанавливаем флаг регистрации
    await db.update_user(user.id, is_registered=True)

    # Если есть новая карта – отправляем QR (опционально)
    if len(cards) == 1 and cards[0]['number'] == card_number:
        qr_photo = await generate_qr_code(card_number)
        caption = f"✅ Ваша бонусная карта:\n{card_number}"
        if isinstance(obj, types.CallbackQuery):
            await obj.message.answer_photo(photo=qr_photo, caption=caption)
        else:
            await obj.answer_photo(photo=qr_photo, caption=caption)

    # Показываем главное меню
    await show_main_menu(
        chat_id=obj.message.chat.id,
        bot=obj.bot,
        state=state,
        user_name=user.first_name_input or "Гость"
    )
