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
from app.services import iiko_service
from app.keyboards.iiko import retry_keyboard
from app.utils.message_utils import safe_edit_message
from app.utils.telegram_helpers import send_safe_message

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
    Показывает информацию о балансе бонусов из iiko.
    """
    await callback.answer()

    # Получаем пользователя из БД
    user = await db.get_user(callback.from_user.id)
    if not user or not user.phone_number:
        text = "❌ У вас не указан номер телефона. Пожалуйста, пройдите регистрацию."
        await safe_edit_message(callback, text, reply_markup=get_back_to_main_keyboard())
        return

    # Запрашиваем информацию о клиенте из iiko
    client_info = await iiko_service.get_customer_info(user.phone_number)

    if client_info is None:
        # Клиент не найден в iiko – возможно, ошибка или ещё не зарегистрирован
        text = (
            "❌ Информация о бонусах временно недоступна.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
        await safe_edit_message(callback, text, reply_markup=get_back_to_main_keyboard())
        return

    # Извлекаем баланс
    balance = client_info.get('balance', 0)
    # Форматируем баланс с двумя знаками после запятой (если нужно)
    formatted_balance = f"{balance:.2f}".replace('.', ',')

    # Поля, которые пока не удаётся получить из API (заглушки)
    expiration_date = "—"
    expiring_bonuses = "—"

    text = (
        f"💰 *Ваш бонусный баланс*\n\n"
        f"Текущие бонусы: {formatted_balance}\n"
        f"Ближайшая дата сгорания: {expiration_date}\n"
        f"Количество бонусов к сгоранию: {expiring_bonuses}\n"
    )

    await safe_edit_message(
        callback,
        text,
        parse_mode="Markdown",
        reply_markup=get_back_to_main_keyboard()
    )


@router.callback_query(lambda c: c.data == "virtual_card")
async def process_virtual_card(callback: types.CallbackQuery):
    """
    Показывает все карты пользователя из iiko с QR-кодами.
    Если карт нет – выпускает автоматически.
    Если клиент не найден в iiko – регистрирует и выпускает карту.
    """

    await callback.answer()

    # Получаем номер телефона пользователя из БД
    user = await db.get_user(callback.from_user.id)
    if not user or not user.phone_number:
        text = "❌ У вас не указан номер телефона. Пожалуйста, пройдите регистрацию через /start"
        await safe_edit_message(callback, text, reply_markup=get_back_to_main_keyboard())
        return

    phone = user.phone_number

    # Запрашиваем информацию о клиенте из iiko
    client_info = await iiko_service.get_customer_info(phone)

    # Если клиент не найден – регистрируем
    if client_info is None:
        # Пытаемся зарегистрировать клиента в iiko
        customer_id, reg_msg = await iiko_service.register_customer(user)
        if not customer_id:
            # Ошибка регистрации – показываем сообщение и кнопку повтора
            text = f"❌ Не удалось зарегистрировать вас в бонусной системе.\nПричина: {reg_msg}\n\nПопробуйте позже."
            await safe_edit_message(callback, text, reply_markup=retry_keyboard())
            return
        # Теперь клиент создан, можно выпускать карту
        client_info = {'customer_id': customer_id, 'cards': []}
    else:
        # Клиент существует – проверяем наличие customer_id
        if not client_info.get('customer_id'):
            # Аномалия – нет ID, пробуем перерегистрировать
            customer_id, reg_msg = await iiko_service.register_customer(user)
            if not customer_id:
                text = f"❌ Ошибка получения данных клиента. Попробуйте позже."
                await safe_edit_message(callback, text, reply_markup=retry_keyboard())
                return
            client_info['customer_id'] = customer_id

    # Теперь у нас есть customer_id (в client_info или полученный)
    customer_id = client_info['customer_id']
    cards = client_info.get('cards', [])

    # Если карт нет – выпускаем
    if not cards:
        success, msg, card_number = await iiko_service.issue_card_for_customer(phone, customer_id)
        if not success:
            text = f"❌ Не удалось выпустить карту.\nПричина: {msg}\n\nПопробуйте позже."
            await safe_edit_message(callback, text, reply_markup=retry_keyboard())
            return
        # Обновляем список карт (можно просто добавить новую, но проще перезапросить)
        client_info = await iiko_service.get_customer_info(phone)
        if not client_info:
            # Если даже после выпуска не получили – странно, но покажем карту
            cards = [{'number': card_number}]
        else:
            cards = client_info.get('cards', [])
            if not cards:
                cards = [{'number': card_number}]

    # Удаляем предыдущее сообщение с кнопками
    await callback.message.delete()

    # Отправляем QR-коды для каждой карты
    for card in cards:
        card_number = card['number']
        qr_photo = await generate_qr_code(card_number)
        caption = f"💳 Карта: {card_number}"
        if card.get('valid_to'):
            caption += f"\nДействует до: {card['valid_to']}"
        await callback.message.answer_photo(
            photo=qr_photo,
            caption=caption
        )

    # Итоговое сообщение
    card_count = len(cards)
    if card_count == 1:
        ending = "карта"
    elif 1 < card_count < 5:
        ending = "карты"
    else:
        ending = "карт"
    final_text = (
        f"✅ Это все ваши бонусные {ending} ({card_count} шт.).\n"
        "Вы можете показать любой QR-код официанту для начисления бонусов.\n\n"
        "*Данная программа лояльности не распространяется на УСЛУГИ ДОСТАВКИ, "
        "столовые 'Ассорти', мастерскую сыра «Страчателли»*"
    )
    await send_safe_message(
        callback,
        final_text,
        reply_markup=get_back_to_main_keyboard()
    )


@router.callback_query(lambda c: c.data == "support")
async def process_support(callback: types.CallbackQuery):
    """Показывает вложенное меню отдела заботы с учётом наличия тикетов"""

    await callback.answer()

    user_id = callback.from_user.id
    tickets_count = await ticket_service.get_user_tickets_count(user_id)
    has_tickets = tickets_count > 0

    text = "🆘 *Отдел заботы*\n\nВыберите действие:"

    await safe_edit_message(
        callback,
        text,
        parse_mode="Markdown",
        reply_markup=get_support_submenu_keyboard(has_tickets=has_tickets)
    )
    await callback.answer()


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

    await safe_edit_message(
        callback,
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=get_back_to_main_keyboard()
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

    await safe_edit_message(
        callback,
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

    await safe_edit_message(
        callback,
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

        # Отправляем уведомление всем модераторам.
        # Используем готовый метод из db для получения модераторов.
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

    # Возвращаем пользователя в главное меню
    await show_main_menu(
        chat_id=message.chat.id,
        bot=message.bot,
        state=state,
        user_name=user.first_name_input or "Гость"
    )


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

    await safe_edit_message(
        callback,
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
    await send_safe_message(callback, text, reply_markup=get_main_menu_keyboard())
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

    text = "🆘 *Отдел заботы*\n\nВыберите действие:"

    await safe_edit_message(
        callback,
        text,
        parse_mode="Markdown",
        reply_markup=get_support_submenu_keyboard(has_tickets=has_tickets)
    )
