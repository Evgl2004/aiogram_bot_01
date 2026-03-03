"""
Хендлеры для системы модерации
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

# Создаем роутер для хендлеров модерации
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
    stats_text = f"""
👨‍💼 Модератор

📬 Новые тикеты: {open_count}
🔄 В работе: {in_progress_count}
"""
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
    stats_text = f"""
👨‍💼 Модератор

📬 Новые тикеты: {open_count}
🔄 В работе: {in_progress_count}
"""
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
    """Список всех тикетов"""
    # Проверяем права модератора
    if not await is_moderator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав модератора", show_alert=True)
        return

    # Получаем все тикеты
    tickets = await ticket_service.get_all_tickets()
    
    if not tickets:
        await callback.message.edit_text(
            """
📭 Нет тикетов

Пока нет вопросов от пользователей.
""",
            reply_markup=ModerationKeyboard.main_menu()
        )
        return
    
    # Формируем текст списка тикетов
    tickets_text = """
📋 Все тикеты

"""
    
    await callback.message.edit_text(
        tickets_text,
        reply_markup=ModerationKeyboard.tickets_list(tickets)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mod_ticket_"))
async def mod_ticket_details(callback: CallbackQuery):
    """Детали тикета"""
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
    
    # Формируем текст с деталями тикета
    username = ticket.user_username or ticket.user_first_name or f"ID:{ticket.user_id}"
    time_created = ticket.created_at.strftime("%d.%m.%Y %H:%M")
    
    ticket_text = f"""
🎫 Тикет #{ticket.id}
👤 Пользователь: {username}
🕐 Создан: {time_created}

❓ Вопрос:
{ticket.message}
"""
    
    await callback.message.edit_text(
        ticket_text,
        reply_markup=ModerationKeyboard.ticket_details(ticket_id)
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
        f"""
📝 Ответ на тикет #{ticket_id}

Введите ваш ответ пользователю:
(Поддерживается HTML форматирование)
""",
        reply_markup=ModerationKeyboard.reply_to_ticket(ticket_id)
    )
    await callback.answer()


@router.message(TicketStates.waiting_for_moderator_reply)
async def mod_send_reply(message: Message, state: FSMContext):
    """Отправка ответа на тикет"""
    # Проверяем права модератора
    if not await is_moderator(message.from_user.id):
        await state.clear()
        await message.answer("❌ У вас нет прав модератора")
        return

    # Получаем данные из состояния
    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    
    if not ticket_id:
        # Это не ответ на тикет, игнорируем
        await state.clear()
        return
    
    # Получаем тикет с обработкой ошибок
    try:
        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            await message.answer("❌ Тикет не найден")
            await state.clear()
            return
    except Exception as e:
        logger.error(f"Ошибка при получении тикета {ticket_id}: {e}")
        await message.answer(f"❌ Ошибка при получении тикета: {e}")
        await state.clear()
        return
    
    # Добавляем сообщение к тикету
    await ticket_service.add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="moderator",
        sender_id=message.from_user.id,
        message=message.text
    )
    
    # Обновляем статус тикета
    await ticket_service.update_ticket_status(ticket_id, "in_progress")
    
    try:
        # Отправляем ответ пользователю
        await message.bot.send_message(
            chat_id=ticket.user_id,
            text=f"""
📬 Ответ на ваш вопрос (тикет #{ticket_id})

📝 Ответ от модератора:
{message.text}
"""
        )
        
        # Отправляем подтверждение модератору
        await message.answer(
            f"""
✅ Ответ отправлен пользователю {ticket.user_username or ticket.user_first_name}

Тикет #{ticket_id} переведен в статус "В работе".
""",
            reply_markup=ModerationKeyboard.after_reply(ticket_id)
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю: {e}")
        await message.answer(
            f"❌ Ошибка при отправке ответа пользователю: {e}",
            reply_markup=ModerationKeyboard.after_reply(ticket_id)
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
    stats_text = f"""
👨‍💼 Модератор

📬 Новые тикеты: {open_count}
🔄 В работе: {in_progress_count}
"""
    if avg_response_time is not None:
        stats_text += f"⏱ Среднее время ответа: {avg_response_time} мин\n"
    else:
        stats_text += "⏱ Среднее время ответа: -\n"
    
    await message.answer(
        stats_text,
        reply_markup=ModerationKeyboard.main_menu()
    )