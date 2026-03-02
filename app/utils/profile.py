"""Общие функции для работы с профилем пользователя"""

from typing import Union
from aiogram import types
from aiogram.fsm.context import FSMContext

from app.database import db
from app.keyboards.registration import get_review_keyboard


async def show_profile_review(obj: Union[types.Message, types.CallbackQuery], state: FSMContext, state_class=None):
    """
    Показывает пользователю его текущие данные в виде анкеты с кнопками «Всё верно» / «Изменить».
    
    Args:
        obj (Union[types.Message, types.CallbackQuery]): Объект сообщения или callback-запроса
        state (FSMContext): Контекст состояния
        state_class: Класс состояния для установки (опционально)
    """

    user_id = obj.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    # Формируем текст анкеты
    gender_text = "мужской" if user.gender == "male" else "женский" if user.gender == "female" else "не указан"
    birth_text = user.birth_date.strftime('%d.%m.%Y') if user.birth_date else "не указана"
    text = (
        "📋 *Проверьте введённые данные:*\n\n"
        f"👤 *Имя:* {user.first_name_input or 'не указано'}\n"
        f"👥 *Фамилия:* {user.last_name_input or 'не указано'}\n"
        f"📞 *Телефон:* {user.phone_number or 'не указан'}\n"
        f"⚥ *Пол:* {gender_text}\n"
        f"🎂 *Дата рождения:* {birth_text}\n"
        f"📧 *Email:* {user.email or 'не указан'}\n\n"
        "Всё верно?"
    )

    if isinstance(obj, types.Message):
        await obj.answer(text, reply_markup=get_review_keyboard(), parse_mode="Markdown")
    else:
        await obj.message.edit_text(text, reply_markup=get_review_keyboard(), parse_mode="Markdown")
        await obj.answer()

    # Устанавливаем состояние, если оно передано
    if state_class:
        await state.set_state(state_class)
