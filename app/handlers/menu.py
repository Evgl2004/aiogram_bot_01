"""
Обработчики главного меню и всех подразделов.
"""

from app.utils.qr import generate_qr_code
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from loguru import logger

from app.database import db
from app.keyboards.menu import (
    get_main_menu_keyboard,
    get_support_submenu_keyboard,
    get_back_to_main_keyboard,
    get_back_to_support_keyboard,
)

router = Router()


# ---------- Главное меню ----------
async def show_main_menu(chat_id: int, bot: Bot, state: FSMContext, user_name: str = "Гость"):
    """
    Отправляет пользователю главное меню.
    Может вызываться из разных мест (например, после регистрации или по команде /start).
    """

    # Очищаем состояние, чтобы выйти из возможных FSM-процессов
    await state.clear()

    text = (
        f"👋 {user_name}, добро пожаловать!\n"
        f"Вы в главном меню.\n"
        "Выберите раздел:"
    )
    # Используем bot.send_message, так как функция может быть вызвана не из хендлера
    await bot.send_message(chat_id, text, reply_markup=get_main_menu_keyboard())


# ---------- Обработчики пунктов главного меню ----------
@router.callback_query(lambda c: c.data == "balance")
async def process_balance(callback: types.CallbackQuery, state: FSMContext):
    """
    Показывает информацию о балансе (заглушка).
    """

    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    # Заглушка, позже данные будут подтягиваться из API
    text = (
        "💰 *Твой баланс*\n\n"
        "Твои бонусы: 0\n"
        "Твой уровень: 3%\n"
        "Ближайшая дата сгорания: —\n"
        "Количество бонусов к сгоранию: —\n"
        "Количество посещений до нового уровня: 3\n"
        "Посещение бани: 0"
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_to_main_keyboard()
    )


@router.callback_query(lambda c: c.data == "virtual_card")
async def process_virtual_card(callback: types.CallbackQuery, state: FSMContext):
    """
    Генерирует и отправляет QR-код с номером телефона пользователя.
    """

    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    phone = user.phone_number or "+70000000000"  # Заглушка, если номера нет

    # Генерируем QR-код
    photo = await generate_qr_code(phone)

    await callback.message.answer_photo(
        photo=photo,
        caption="🪪 Ваш QR-код для предъявления на кассе.\n"
                f"Номер телефона: {phone}",
        reply_markup=get_back_to_main_keyboard()
    )
    # Удаляем предыдущее сообщение с кнопками (чтобы не захламлять)
    await callback.message.delete()


@router.callback_query(lambda c: c.data == "support")
async def process_support(callback: types.CallbackQuery, state: FSMContext):
    """
    Показывает подменю отдела заботы.
    """

    await callback.answer()
    await callback.message.edit_text(
        "🆘 *Отдел заботы*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_support_submenu_keyboard()
    )


@router.callback_query(lambda c: c.data == "vacancies")
async def process_vacancies(callback: types.CallbackQuery, state: FSMContext):
    """
    Показывает информацию о вакансиях и ссылку.
    """

    await callback.answer()
    text = (
        "💼 *Вакансии*\n\n"
        "Ждем классных, ответственных, позитивных, энергичных и профессиональных "
        "сотрудников в дружные команды наших заведений!\n\n"
        "Гарантируем:\n"
        "• крепкие коллективы, в которых весело работать и приятно отдыхать после смены\n"
        "• с нами – непрерывное профессиональное развитие\n"
        "• мы не дадим скучать и хандрить\n"
        "• достойный доход и щедрые чаевые\n\n"
        "Если чувствуешь, что хочешь работать в заведениях самого уютного и надёжного "
        "бренда Тюмени – переходи по ссылке и оставляй заявку!\n\n"
        "👉 [Посмотреть все вакансии](https://team.sobolevalliance.su/vacancy)"
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_to_main_keyboard(),
        disable_web_page_preview=True
    )


# ---------- Обработчики подменю отдела заботы ----------
@router.callback_query(lambda c: c.data == "support_feedback")
async def process_feedback(callback: types.CallbackQuery, state: FSMContext):
    """
    Отправляет ссылку на внешний сервис отзывов.
    """

    await callback.answer()
    text = (
        "✍️ *Оставить отзыв*\n\n"
        "Мы будем рады узнать ваше мнение! Перейдите по ссылке ниже:\n"
        "👉 [Форма обратной связи](https://example.com/feedback) (ссылка будет заменена)"
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_to_support_keyboard(),
        disable_web_page_preview=True
    )


@router.callback_query(lambda c: c.data == "support_question")
async def process_question(callback: types.CallbackQuery, state: FSMContext):
    """
    Заглушка для функции 'Мне только спросить'.
    """

    await callback.answer()
    text = (
        "❓ *Мне только спросить*\n\n"
        "Эта функция находится в разработке. Скоро вы сможете задать вопрос "
        "оператору прямо в Telegram."
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_to_support_keyboard()
    )


@router.callback_query(lambda c: c.data == "support_contacts")
async def process_contacts(callback: types.CallbackQuery, state: FSMContext):
    """
    Показывает контактную информацию.
    """

    await callback.answer()
    text = (
        "📧 Контакты\n\n"
        "Почта для связи: brand@ermolaev.beer\n"
        "Сайт: https://ermolaev.beer\n"
        "Соцсети: @ermolaev_beer"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_support_keyboard()
    )


# ---------- Навигационные кнопки ----------
@router.callback_query(lambda c: c.data == "back_to_main")
async def process_back_to_main(callback: types.CallbackQuery, state: FSMContext):
    """
    Возврат в главное меню.
    """

    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    name = user.first_name_input or "Гость"
    text = f"👋 {name}, вы в главном меню.\nВыберите раздел:"
    # Отправляем новое сообщение с главным меню
    await callback.message.answer(text, reply_markup=get_main_menu_keyboard())
    # Удаляем текущее сообщение (с которого пришёл callback)
    await callback.message.delete()


@router.callback_query(lambda c: c.data == "back_to_support")
async def process_back_to_support(callback: types.CallbackQuery, state: FSMContext):
    """
    Возврат в подменю отдела заботы.
    """

    await callback.answer()
    await callback.message.edit_text(
        "🆘 *Отдел заботы*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_support_submenu_keyboard()
    )
