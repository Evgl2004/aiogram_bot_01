"""
Обработчики для системы модерации
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.database import db
from app.services.tickets import ticket_service
from app.keyboards.moderation import ModerationKeyboard
from app.states.tickets import TicketStates

from app.utils.validation import confirm_text
from app.utils.ticket_formatter import format_ticket_details
import html

# Создаем роутер для Обработчика модерации
router = Router()


async def is_moderator(user_id: int) -> bool:
    """Проверка, является ли пользователь модератором"""
    return await db.is_user_moderator(user_id)


@router.message(F.text == "👨‍💼 Модератор")
async def moderator_menu(message: Message):
    """Меню модератора"""
    # Проверяем права модератора
    if not await is_moderator(message.from_user.id):
        await message.answer("❌ У вас нет прав модератора")
        return

    # Получаем статистику по тикетам
    open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
    
    # Формируем текст статистики
    stats_text = (
        f"👨‍💼 *Модератор*\n\n"
        f"📬 Новые тикеты: {open_count}\n"
        f"🔄 В работе: {in_progress_count}\n"
    )
    if avg_response_time is not None:
        stats_text += f"⏱ Среднее время ответа: {avg_response_time} мин\n"
    else:
        stats_text += "⏱ Среднее время ответа: -\n"
    
    await message.answer(
        stats_text,
        reply_markup=ModerationKeyboard.main_menu()
    )


@router.callback_query(F.data == "mod_main")
async def mod_main_callback(callback: CallbackQuery):
    """Главное меню модератора (callback)"""
    # Проверяем права модератора
    if not await is_moderator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав модератора", show_alert=True)
        return

    # Получаем статистику по тикетам
    open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
    
    # Формируем текст статистики
    stats_text = (
        f"👨‍💼 *Модератор*\n\n"
        f"📬 Новые тикеты: {open_count}\n"
        f"🔄 В работе: {in_progress_count}\n"
    )
    if avg_response_time is not None:
        stats_text += f"⏱ Среднее время ответа: {avg_response_time} мин\n"
    else:
        stats_text += "⏱ Среднее время ответа: -\n"
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=ModerationKeyboard.main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "mod_tickets")
async def mod_tickets_list(callback: CallbackQuery):
    """
    Обработчик кнопки «Все тикеты» – показывает первую страницу списка.
    """
    # Проверяем права модератора
    if not await is_moderator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав модератора", show_alert=True)
        return

    # Получаем первую страницу тикетов (по умолчанию 10 тикетов на странице)
    tickets, total_count = await ticket_service.get_tickets_page(page=1, per_page=10)
    total_pages = (total_count + 10 - 1) // 10  # вычисляем общее количество страниц

    if not tickets:
        # Если тикетов нет вообще, показываем сообщение и меню
        await callback.message.edit_text(
            "📭 Нет тикетов",
            reply_markup=ModerationKeyboard.main_menu()
        )
        await callback.answer()
        return

    # Формируем текст с указанием текущей страницы
    text = f"📋 Все тикеты (страница 1/{total_pages}):"
    await callback.message.edit_text(
        text,
        reply_markup=ModerationKeyboard.tickets_list(tickets, current_page=1, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mod_tickets_page_"))
async def mod_tickets_page(callback: CallbackQuery):
    """
    Обработчик переключения страниц списка тикетов.
    Ожидает callback_data вида "mod_tickets_page_2", где 2 – номер страницы.
    """
    # Проверяем права модератора
    if not await is_moderator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав модератора", show_alert=True)
        return

    # Извлекаем номер страницы из callback_data (последний элемент после '_')
    try:
        page = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Ошибка в номере страницы", show_alert=True)
        return

    # Получаем тикеты для запрошенной страницы
    tickets, total_count = await ticket_service.get_tickets_page(page=page, per_page=10)
    total_pages = (total_count + 10 - 1) // 10

    if not tickets:
        # Если на странице нет тикетов (возможно, удалили последний), показываем сообщение
        await callback.message.edit_text(
            "📭 На этой странице нет тикетов",
            reply_markup=ModerationKeyboard.main_menu()
        )
        await callback.answer()
        return

    # Формируем текст с номером текущей страницы
    text = f"📋 Все тикеты (страница {page}/{total_pages}):"
    await callback.message.edit_text(
        text,
        reply_markup=ModerationKeyboard.tickets_list(tickets, current_page=page, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mod_ticket_"))
async def mod_ticket_details(callback: CallbackQuery):
    """
    Показывает детальную информацию по тикету, включая всю историю переписки.
    """

    # Проверяем права модератора
    if not await is_moderator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав модератора", show_alert=True)
        return

    # Извлекаем ID тикета из callback_data (ожидается mod_ticket_123)
    try:
        ticket_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Получаем тикет
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("❌ Тикет не найден", show_alert=True)
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)

    # Форматируем через общую функцию
    ticket_text = format_ticket_details(ticket, messages)

    await callback.message.edit_text(
        ticket_text,
        parse_mode="HTML",
        reply_markup=ModerationKeyboard.ticket_details(ticket_id, ticket.status)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mod_reply_"))
async def mod_reply_to_ticket(callback: CallbackQuery, state: FSMContext):
    """Ответ на тикет"""
    # Проверяем права модератора
    if not await is_moderator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав модератора", show_alert=True)
        return

    # Извлекаем ID тикета из callback_data
    ticket_id = int(callback.data.split("_")[-1])
    
    # Получаем тикет
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    
    # Сохраняем ID тикета в состоянии
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(TicketStates.waiting_for_moderator_reply)

    # Отправляем сообщение с просьбой ввести ответ
    await callback.message.edit_text(
        f"📝 *Ответ на тикет #{ticket_id}*\n\n"
        f"Введите ваш ответ пользователю:\n"
        f"(Поддерживается HTML форматирование)",
        reply_markup=ModerationKeyboard.reply_to_ticket(ticket_id)
    )
    await callback.answer()


@router.message(TicketStates.waiting_for_moderator_reply)
async def mod_send_reply(message: Message, state: FSMContext):
    # Проверка текста
    if not await confirm_text(message, "✍️ Пожалуйста, отправьте ответ текстовым сообщением."):
        return

    # Проверка прав модератора
    if not await is_moderator(message.from_user.id):
        await state.clear()
        await message.answer("❌ У вас нет прав модератора")
        return

    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    if not ticket_id:
        await state.clear()
        return

    # Получаем тикет
    try:
        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            await message.answer("❌ Тикет не найден")
            await state.clear()
            return
    except Exception as e:
        logger.error(f"Ошибка при получении тикета {ticket_id}: {e}")
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()
        return

    # Сохраняем ответ в историю
    await ticket_service.add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="moderator",
        sender_id=message.from_user.id,
        message=message.text
    )

    # Обновляем статус
    await ticket_service.update_ticket_status(ticket_id, "in_progress")

    # Отправляем ответ пользователю
    try:
        await message.bot.send_message(
            chat_id=ticket.user_id,
            text=(
                f"📬 <b>Ответ на ваш вопрос</b> (тикет #{ticket_id})\n\n"
                f"📝 <b>Ответ от модератора:</b>\n"
                f"{html.escape(message.text)}"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю: {e}")
        # Продолжаем, чтобы показать модератору обновлённый тикет

    # Получаем всю историю сообщений
    messages = await ticket_service.get_ticket_messages(ticket_id)

    ticket_text = format_ticket_details(ticket, messages)

    # Отправляем модератору
    await message.answer(
        ticket_text,
        parse_mode="HTML",
        reply_markup=ModerationKeyboard.ticket_details(ticket_id, ticket.status)
    )

    # Очищаем состояние
    await state.clear()


# Команда для модератора
@router.message(Command("mod"))
async def mod_command(message: Message):
    """Команда для открытия меню модератора"""
    # Проверяем права модератора
    if not await is_moderator(message.from_user.id):
        await message.answer("❌ У вас нет прав модератора")
        return

    # Получаем статистику по тикетам
    open_count, in_progress_count, avg_response_time = await ticket_service.get_tickets_stats()
    
    # Формируем текст статистики
    stats_text = (
        f"👨‍💼 *Модератор*\n\n"
        f"📬 Новые тикеты: {open_count}\n"
        f"🔄 В работе: {in_progress_count}\n"
    )
    if avg_response_time is not None:
        stats_text += f"⏱ Среднее время ответа: {avg_response_time} мин\n"
    else:
        stats_text += "⏱ Среднее время ответа: -\n"
    
    await message.answer(
        stats_text,
        reply_markup=ModerationKeyboard.main_menu()
    )


@router.callback_query(F.data.startswith("mod_close_"))
async def mod_close_ticket(callback: CallbackQuery):
    """Закрыть тикет (установить статус closed и время закрытия)"""
    # Проверяем права модератора
    if not await is_moderator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав модератора", show_alert=True)
        return

    # Извлекаем ID тикета
    ticket_id = int(callback.data.split("_")[-1])

    # Закрываем тикет через сервис
    success = await ticket_service.close_ticket(ticket_id)
    if not success:
        await callback.answer("❌ Тикет не найден", show_alert=True)
        return

    await callback.answer("✅ Тикет закрыт")

    # Получаем обновлённый тикет для отображения
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        await callback.message.edit_text("❌ Ошибка при загрузке тикета")
        return

    # Получаем сообщения (историю)
    messages = await ticket_service.get_ticket_messages(ticket_id)

    # Формируем текст аналогично mod_ticket_details
    ticket_text = format_ticket_details(ticket, messages)

    await callback.message.edit_text(
        ticket_text,
        parse_mode="HTML",
        reply_markup=ModerationKeyboard.ticket_details(ticket_id, ticket.status)
    )
