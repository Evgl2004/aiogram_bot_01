"""
Обработчик команды /start с проверкой регистрации и согласий
"""

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.database import db
from app.keyboards.registration import get_rules_keyboard, get_contact_keyboard
from app.states.registration import Registration
from app.states.legacy import LegacyUpgrade

from app.handlers.menu import show_main_menu
from app.handlers.legacy import start_legacy_upgrade

router = Router()


async def _handle_start_logic(message: Message, state: FSMContext) -> None:
    """
    Общая логика обработки запуска бота.
    Вызывается из команды /start и может быть вызвана из других точек входа
    (например, из события bot_started).
    """
    user = message.from_user
    user_id = user.id
    logger.info(f"Пользователь user_id={user_id} запустил бот")

    # Сохраняем или обновляем пользователя в базе данных
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Получаем полные данные пользователя из БД
    db_user = await db.get_user(user_id)
    if not db_user:
        logger.error(f"Пользователь user_id={user_id} не найден после добавления в БД")
        return

    # Сброс застрявших состояний регистрации/легаси ---
    current_state = await state.get_state()
    if db_user.is_registered and not db_user.is_legacy:
        # Если пользователь уже зарегистрирован, но почему-то остался в состоянии ожидания iiko
        if current_state in [
            Registration.waiting_for_iiko_registration.state,
            LegacyUpgrade.waiting_for_iiko_registration.state
        ]:
            logger.info(f"Сбрасываем застрявшее состояние iiko для пользователя {user_id}")
            await state.clear()
            current_state = None  # обновляем переменную для последующих проверок

    # Проверка, является ли пользователь устаревшим (legacy)
    if db_user.is_registered and db_user.is_legacy:
        logger.info(f"Устаревший пользователь user_id={user_id} запустил бот, запускаем процесс обновления данных")
        await start_legacy_upgrade(message, state, db_user)
        return

    # Проверка согласия с правилами
    if not db_user.rules_accepted:
        # --- Сброс неожиданных состояний при непринятых правилах ---
        if current_state is not None and current_state != Registration.waiting_for_rules_consent.state:
            logger.info(f"Сбрасываем неожиданное состояние {current_state} для "
                        f"пользователя {user_id} (правила не приняты)")
            await state.clear()
        # Отправляем сообщение с правилами и устанавливаем состояние ожидания согласия
        await message.answer(
            "👋 Здравствуй Друг!\n\n"
            "Добро пожаловать к нам в гости!\n\n"
            "📜 Для начала нам необходимо получить твоё согласие на обработку персональных данных "
            "и согласие с политикой конфиденциальности.\n\n"
            "👉 Ознакомься с документами по ссылке ниже и нажми «✅ Согласен».",
            reply_markup=get_rules_keyboard()
        )
        await state.set_state(Registration.waiting_for_rules_consent)
        return

    # Проверка завершённости регистрации
    if not db_user.is_registered:
        await message.answer(
            "📱 Чтобы подключиться к программе лояльности, нажми кнопку «Поделиться контактом».\n"
            "После этого мы будем знакомы чуть ближе.",
            reply_markup=get_contact_keyboard()
        )
        await state.set_state(Registration.waiting_for_contact)
        return

    # Если регистрация завершена (и пользователь не legacy)
    await show_main_menu(
        chat_id=message.chat.id,
        bot=message.bot,
        state=state,
        user_name=db_user.first_name_input or "Гость"
    )


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    Вызывает общую логику _handle_start_logic.
    """
    await _handle_start_logic(message, state)
