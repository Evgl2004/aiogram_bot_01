"""
Обработчики главного меню и всех подразделов.
"""

from app.utils.qr import generate_qr_code
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from loguru import logger

from app.database import db
from app.services.tickets import ticket_service
from app.keyboards.menu import (
    get_main_menu_keyboard,
    get_support_submenu_keyboard,
    get_back_to_main_keyboard,
    get_back_to_support_keyboard,
)
from app.states.tickets import TicketStates
from app.utils.validation import confirm_text

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
    # Используем bot.send_message, так как функция может быть вызвана не из Обработчика
    await bot.send_message(chat_id, text, reply_markup=get_main_menu_keyboard())


# ---------- Обработчики пунктов главного меню ----------
@router.callback_query(lambda c: c.data == "balance")
async def process_balance(callback: types.CallbackQuery):
    """
    Показывает информацию о балансе (заглушка).
    """

    await callback.answer()
    # Заглушка, позже данные будут подтягиваться из API
    text = (
        "💰 *Твой баланс*\n\n"
        "Твои бонусы: 0\n"
        "Твой уровень: 3%\n"
        "Ближайшая дата сгорания: —\n"
        "Количество бонусов к сгоранию: —\n"
        "Количество посещений до нового уровня: 3\n"
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_to_main_keyboard()
    )


@router.callback_query(lambda c: c.data == "virtual_card")
async def process_virtual_card(callback: types.CallbackQuery):
    """
    Генерирует и отправляет QR-код с номером телефона пользователя.
    """

    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

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
async def process_support(callback: types.CallbackQuery):
    """Показывает вложенное меню отдела заботы с учётом наличия тикетов"""
    await callback.answer()

    user_id = callback.from_user.id
    tickets_count = await ticket_service.get_user_tickets_count(user_id)
    has_tickets = tickets_count > 0

    await callback.message.edit_text(
        "🆘 *Отдел заботы*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_support_submenu_keyboard(has_tickets=has_tickets)
    )


@router.callback_query(lambda c: c.data == "vacancies")
async def process_vacancies(callback: types.CallbackQuery):
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
async def process_feedback(callback: types.CallbackQuery):
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
    Обработчик функции 'Мне только спросить' - создание тикета.
    """

    await callback.answer()

    # Сохраняем состояние для ожидания вопроса
    await state.set_state(TicketStates.waiting_for_question)

    text = (
        "❓ *Мне только спросить*\n\n"
        "Пожалуйста, отправьте ваш вопрос, и наш модератор свяжется с вами в ближайшее время.\n\n"
        "Введите ваш вопрос:"
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_to_support_keyboard()
    )


@router.message(TicketStates.waiting_for_question)
async def process_question_text(message: types.Message, state: FSMContext):
    """
    Обработчик текста вопроса от пользователя.
    """

    # Проверка ввода только текста
    if not await confirm_text(message, "✍️ Пожалуйста, введите вопрос текстовым сообщением."):
        return

    # Получаем информацию о пользователе
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    # Создаем тикет
    ticket = await ticket_service.create_ticket(
        user_id=message.from_user.id,
        message=message.text,
        user_username=message.from_user.username,
        user_first_name=message.from_user.first_name or user.first_name_input
    )

    # Отправляем подтверждение пользователю
    await message.answer(
        f"📨 Ваш вопрос принят!\n\n"
        f"🎫 Создан тикет #{ticket.id}\n"
        f"🕐 Модератор рассмотрит ваш вопрос в ближайшее время.\n\n"
        f"Вы получите уведомление с ответом."
    )

    # Уведомляем модераторов о новом тикете
    try:
        # Получаем статистику по тикетам
        open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()

        # Формируем текст уведомления
        notification_text = (
            f"📬 *Новый тикет от пользователя!*\n\n"
            f"🎫 Тикет #{ticket.id}\n"
            f"👤 Пользователь: {message.from_user.username or message.from_user.first_name}\n"
            f"❓ Вопрос: {message.text[:100]}{'...' if len(message.text) > 100 else ''}\n\n"
            f"📊 *Статистика:*\n"
            f"📬 Новые тикеты: {open_count}\n"
            f"🔄 В работе: {in_progress_count}\n"
        )

        # Отправляем уведомление всем модераторам
        # Используем готовый метод из db для получения модераторов
        moderators = await db.get_moderators()

        for moderator in moderators:
            try:
                await message.bot.send_message(
                    chat_id=moderator.id,
                    text=notification_text
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления модератору {moderator.id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления модераторам: {e}")

    # Очищаем состояние
    await state.clear()


@router.callback_query(lambda c: c.data == "support_contacts")
async def process_contacts(callback: types.CallbackQuery):
    """
    Показывает контактную информацию.
    """

    await callback.answer()
    text = (
        "📧 Контакты:\n\n"
        "Почта для связи: info@sobolev.rest\n"
        "Сайт: https://sobolevalliance.su\n"
        "Соцсети: @sobolevalliance"
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
    # Очищаем состояние при возврате в главное меню
    await state.clear()

    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    name = user.first_name_input or "Гость"
    text = f"👋 {name}, вы в главном меню.\nВыберите раздел:"
    # Отправляем новое сообщение с главным меню
    await callback.message.answer(text, reply_markup=get_main_menu_keyboard())
    # Удаляем текущее сообщение (с которого пришёл callback)
    await callback.message.delete()


@router.callback_query(lambda c: c.data == "back_to_support")
async def process_back_to_support(callback: types.CallbackQuery, state: FSMContext):
    """
    Возврат во вложенный отдел заботы.
    """

    await callback.answer()
    # Очищаем состояние при возврате в отдел заботы
    await state.clear()

    user_id = callback.from_user.id
    tickets_count = await ticket_service.get_user_tickets_count(user_id)
    has_tickets = tickets_count > 0

    await callback.message.edit_text(
        "🆘 *Отдел заботы*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_support_submenu_keyboard(has_tickets=has_tickets)
    )
