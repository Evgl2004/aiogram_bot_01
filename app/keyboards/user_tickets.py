from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.database.models import Ticket
from typing import List


class UserTicketsKeyboard:
    """Клавиатуры для раздела «Мои обращения»"""

    @staticmethod
    def tickets_list(tickets: List[Ticket], current_page: int, total_pages: int) -> InlineKeyboardMarkup:
        """Список тикетов с пагинацией"""
        builder = InlineKeyboardBuilder()

        for ticket in tickets:
            status_emoji = {
                "open": "🆕",
                "in_progress": "🔄",
                "closed": "🔒"
            }.get(ticket.status, "❓")
            # Краткое описание: дата, статус, первые 20 символов вопроса
            short_question = (ticket.message[:20] + "…") if len(ticket.message) > 20 else ticket.message
            button_text = f"{status_emoji} #{ticket.id} от {ticket.created_at.strftime('%d.%m')}: {short_question}"
            builder.row(InlineKeyboardButton(
                text=button_text,
                callback_data=f"user_ticket_{ticket.id}"
            ))

        # Кнопки пагинации
        nav_row = []
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(
                text="⬅️ Предыдущая",
                callback_data=f"user_tickets_page_{current_page - 1}"
            ))
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(
                text="Следующая ➡️",
                callback_data=f"user_tickets_page_{current_page + 1}"
            ))
        if nav_row:
            builder.row(*nav_row)

        # Кнопка возврата в отдел заботы
        builder.row(InlineKeyboardButton(
            text="🔙 Назад в отдел заботы",
            callback_data="back_to_support"
        ))

        return builder.as_markup()

    @staticmethod
    def back_to_support() -> InlineKeyboardMarkup:
        """Простая клавиатура с кнопкой назад в отдел заботы"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🔙 Назад в отдел заботы",
            callback_data="back_to_support"
        ))
        return builder.as_markup()

    @staticmethod
    def ticket_details(ticket_id: int, status: str) -> InlineKeyboardMarkup:
        """Клавиатура для просмотра деталей тикета пользователем"""

        builder = InlineKeyboardBuilder()
        if status != 'closed':
            builder.row(InlineKeyboardButton(
                text="📝 Ответить",
                callback_data=f"user_reply_{ticket_id}"
            ))
        builder.row(InlineKeyboardButton(
            text="🔙 Назад к списку",
            callback_data="my_tickets"
        ))
        return builder.as_markup()

    @staticmethod
    def cancel_reply(ticket_id: int) -> InlineKeyboardMarkup:
        """Клавиатура для отмены ответа на тикет"""

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"user_ticket_{ticket_id}"
        ))
        return builder.as_markup()

    @staticmethod
    def notification_keyboard(ticket_id: int, status: str) -> InlineKeyboardMarkup:
        """Клавиатура для уведомления пользователя о новом ответе модератора"""

        builder = InlineKeyboardBuilder()
        if status != 'closed':
            builder.row(InlineKeyboardButton(
                text="📝 Ответить",
                callback_data=f"user_reply_{ticket_id}"
            ))
        builder.row(InlineKeyboardButton(
            text="📋 Мои обращения",
            callback_data="my_tickets"
        ))
        return builder.as_markup()
