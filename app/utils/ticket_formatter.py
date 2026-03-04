import html
from typing import List, Optional
from app.database.models import Ticket, TicketMessage


def format_ticket_details(ticket: Ticket, messages: Optional[List[TicketMessage]] = None) -> str:
    """
    Форматирует детали тикета с историей переписки в HTML для отправки в Telegram.
    """

    # Экранируем основные поля
    username = html.escape(ticket.user_username or ticket.user_first_name or f"ID:{ticket.user_id}")
    time_created = ticket.created_at.strftime("%d.%m.%Y %H:%M")
    question = html.escape(ticket.message)

    # Эмодзи статуса
    status_emoji = {
        "open": "🆕",
        "in_progress": "🔄",
        "closed": "🔒"
    }.get(ticket.status, "❓")

    # Базовая информация
    details = (
        f"{status_emoji} <b>Тикет #{ticket.id}</b>\n"
        f"👤 <b>Пользователь:</b> {username}\n"
        f"🕐 <b>Создан:</b> {time_created}\n"
        f"📌 <b>Статус:</b> {localize_status(ticket.status)}\n\n"
        f"❓ <b>Вопрос:</b>\n"
        f"{question}"
    )

    # История переписки
    if messages:
        details += "\n\n--- <b>Переписка</b> ---"
        for msg in messages:
            sender = "👤 <b>Пользователь</b>" if msg.sender_type == "user" else "👨‍💼 <b>Модератор</b>"
            time_msg = msg.created_at.strftime("%d.%m %H:%M")
            escaped_text = html.escape(msg.message)
            details += f"\n\n[{time_msg}] {sender}:\n<blockquote>{escaped_text}</blockquote>"

    # Время закрытия
    if ticket.status == "closed" and ticket.closed_at:
        closed_time = ticket.closed_at.strftime("%d.%m.%Y %H:%M")
        details += f"\n\n🔒 <b>Закрыт:</b> {closed_time}"

    return details


def localize_status(status: str) -> str:
    """Переводит статус тикета на русский язык"""

    status_map = {
        "open": "Открыт",
        "in_progress": "В работе",
        "closed": "Закрыт"
    }
    return status_map.get(status, status)