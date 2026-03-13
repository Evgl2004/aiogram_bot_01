"""
Обработчики для пользовательского раздела "Мои обращения"
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.database import db
from app.database.models import Ticket
from aiogram import Bot

from app.services.tickets import ticket_service
from app.keyboards.user_tickets import UserTicketsKeyboard
from app.utils.ticket_formatter import format_ticket_details
from app.states.tickets import UserTicketStates
from app.utils.validation import confirm_text
from app.utils.message_utils import safe_edit_message
import html

router = Router()


@router.callback_query(F.data == "my_tickets")
async def user_tickets_list(callback: CallbackQuery):
    """
    Показывает первую страницу списка тикетов текущего пользователя.
    """

    user_id = callback.from_user.id

    # Получаем первую страницу тикетов пользователя
    tickets, total_count = await ticket_service.get_tickets_page(
        page=1,
        per_page=5,  # для пользователя можно меньше, чем для модератора
        user_id=user_id
    )
    total_pages = (total_count + 5 - 1) // 5

    if not tickets:
        text = (
            "📭 У вас пока нет обращений.\n\n"
            "Чтобы создать обращение, нажмите «❓ Мне только спросить» в меню отдела заботы."
        )
        await safe_edit_message(
            callback,
            text,
            reply_markup=UserTicketsKeyboard.back_to_support()
        )
        await callback.answer()
        return

    text = f"📋 Ваши обращения (страница 1/{total_pages}):"
    await safe_edit_message(
        callback,
        text,
        reply_markup=UserTicketsKeyboard.tickets_list(tickets, current_page=1, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_tickets_page_"))
async def user_tickets_page(callback: CallbackQuery):
    """
    Обработчик переключения страниц списка тикетов пользователя.
    """

    try:
        page = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    tickets, total_count = await ticket_service.get_tickets_page(
        page=page,
        per_page=5,
        user_id=user_id
    )
    total_pages = (total_count + 5 - 1) // 5

    if not tickets:
        text = "📭 На этой странице нет обращений."
        await safe_edit_message(
            callback,
            text,
            reply_markup=UserTicketsKeyboard.back_to_support()
        )
        await callback.answer()
        return

    text = f"📋 Ваши обращения (страница {page}/{total_pages}):"
    await safe_edit_message(
        callback,
        text,
        reply_markup=UserTicketsKeyboard.tickets_list(tickets, current_page=page, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_ticket_"))
async def user_ticket_details(callback: CallbackQuery):
    """Показывает детали тикета для пользователя"""

    try:
        ticket_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный формат", show_alert=True)
        return

    # Проверяем, что тикет принадлежит текущему пользователю
    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != callback.from_user.id:
        await callback.answer("❌ Тикет не найден или доступ запрещён", show_alert=True)
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    await safe_edit_message(
        callback,
        ticket_text,
        parse_mode="HTML",
        reply_markup=UserTicketsKeyboard.ticket_details(ticket_id, ticket.status)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_reply_"))
async def user_reply_to_ticket(callback: CallbackQuery, state: FSMContext):
    """Начало ответа на тикет пользователем"""

    try:
        ticket_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != callback.from_user.id:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    if ticket.status == 'closed':
        await callback.answer("❌ Тикет закрыт, ответ невозможен", show_alert=True)
        return

    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(UserTicketStates.waiting_for_reply)

    text = (
        f"📝 *Ответ на тикет #{ticket_id}*\n\n"
        f"Введите ваш ответ:"
    )

    # Отправляем сообщение и сохраняем его ID для последующего удаления
    try:
        sent_msg = await callback.message.edit_text(
            text,
            reply_markup=UserTicketsKeyboard.cancel_reply(ticket_id),
            parse_mode="Markdown"
        )
    except Exception:
        sent_msg = await callback.message.answer(
            text,
            reply_markup=UserTicketsKeyboard.cancel_reply(ticket_id),
            parse_mode="Markdown"
        )

    # Сохраняем ID сообщения с клавиатурой отмены в состоянии
    await state.update_data(cancel_message_id=sent_msg.message_id)

    await callback.answer()


@router.message(UserTicketStates.waiting_for_reply)
async def user_send_reply(message: Message, state: FSMContext):
    """
    Обрабатывает ответ пользователя на тикет.

    Функция выполняет следующие шаги:
    1. Проверяет, что сообщение текстовое (через confirm_text).
    2. Извлекает ID тикета из состояния FSM.
    3. Проверяет существование тикета и его принадлежность текущему пользователю.
    4. Сохраняет сообщение в таблицу ticket_messages с типом отправителя "user".
    5. Если тикет находился в статусе "open", обновляет его на "in_progress",
       чтобы модератор видел, что диалог активен.
    6. Отправляет уведомление всем модераторам о новом сообщении от пользователя.
    7. Запрашивает обновлённую историю переписки и формирует карточку тикета.
    8. Отправляет пользователю актуальное состояние тикета с клавиатурой для дальнейших действий.
    9. Очищает состояние FSM.
    """

    if not await confirm_text(message, "✍️ Пожалуйста, отправьте текстовое сообщение."):
        return

    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    if not ticket_id:
        await state.clear()
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != message.from_user.id:
        await message.answer("❌ Ошибка доступа")
        await state.clear()
        return

    # Сохраняем ответ пользователя в историю
    await ticket_service.add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="user",
        sender_id=message.from_user.id,
        message=message.text
    )

    # Если тикет был открыт, переводим его в статус "в работе"
    if ticket.status == 'open':
        await ticket_service.update_ticket_status(ticket_id, 'in_progress')

    # Уведомляем модераторов о новом сообщении
    await notify_moderators_new_message(message.bot, ticket, message.text)

    # Получаем обновлённую историю переписки
    messages = await ticket_service.get_ticket_messages(ticket_id)
    ticket_text = format_ticket_details(ticket, messages)

    # Удаляем сообщение с кнопкой "Отмена", если оно было сохранено
    cancel_msg_id = data.get("cancel_message_id")
    if cancel_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=cancel_msg_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение отмены: {e}")

    # Отправляем пользователю обновлённую карточку тикета
    await message.answer(
        ticket_text,
        parse_mode="HTML",
        reply_markup=UserTicketsKeyboard.ticket_details(ticket_id, ticket.status)
    )
    await state.clear()


async def notify_moderators_new_message(bot: Bot, ticket: Ticket, message_text: str):
    """
    Уведомляет всех модераторов о новом сообщении от пользователя в тикете.
    """

    try:
        moderators = await db.get_moderators()
        for moderator in moderators:
            try:
                await bot.send_message(
                    chat_id=moderator.id,
                    text=(
                        f"📬 <b>Новое сообщение от пользователя</b>\n\n"
                        f"🎫 Тикет #{ticket.id}\n"
                        f"👤 Пользователь: {html.escape(ticket.user_username or ticket.user_first_name or str(ticket.user_id))}\n"
                        f"💬 Сообщение: {html.escape(message_text[:100])}{'…' if len(message_text) > 100 else ''}"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления модератора {moderator.id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении списка модераторов: {e}")
