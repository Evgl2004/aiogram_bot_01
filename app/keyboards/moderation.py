"""
Клавиатуры для системы модерации
"""

from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.database.models import Ticket


class ModerationKeyboard:
    """Клавиатуры для системы модерации"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Главное меню модератора"""
        keyboard = [
            [InlineKeyboardButton(text="📋 Все тикеты", callback_data="mod_tickets")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    def tickets_list(
            tickets: List[Ticket],
            current_page: int = 1,
            total_pages: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создаёт клавиатуру со списком тикетов и кнопками пагинации.

        :param tickets: Список тикетов для отображения на текущей странице
        :param current_page: Номер текущей страницы
        :param total_pages: Общее количество страниц
        :return: InlineKeyboardMarkup с кнопками тикетов и навигации
        """
        keyboard = []

        # --- Кнопки для каждого тикета ---
        for ticket in tickets:
            # Выбираем эмодзи в зависимости от статуса
            status_emoji = {
                "open": "🆕",
                "in_progress": "🔄",
                "closed": "🔒"
            }.get(ticket.status, "❓")

            # Формируем подпись: эмодзи, номер тикета, имя пользователя, время
            username = ticket.user_username or ticket.user_first_name or f"ID:{ticket.user_id}"
            time_ago = ModerationKeyboard._format_time_ago(ticket.created_at)
            button_text = f"{status_emoji} #{ticket.id} от {username} ({time_ago})"

            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"mod_ticket_{ticket.id}"
                )
            ])

        # --- Кнопки навигации по страницам ---
        # Добавляются только если есть несколько страниц
        nav_buttons = []
        if current_page > 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Предыдущая",
                    callback_data=f"mod_tickets_page_{current_page - 1}"
                )
            )
        if current_page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Следующая ➡️",
                    callback_data=f"mod_tickets_page_{current_page + 1}"
                )
            )
        if nav_buttons:
            keyboard.append(nav_buttons)

        # --- Кнопка возврата в главное меню модератора ---
        keyboard.append([
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="mod_main")
        ])

        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def ticket_details(ticket_id: int, status: str = None) -> InlineKeyboardMarkup:
        """
        Клавиатура для детального просмотра тикета.
        Если тикет закрыт (status='closed'), кнопки ответа и закрытия не показываются.
        """
        keyboard = []

        # Кнопки доступны только для открытых и в работе
        if status != 'closed':
            keyboard.append([InlineKeyboardButton(text="📩 Ответить", callback_data=f"mod_reply_{ticket_id}")])
            keyboard.append([InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"mod_close_{ticket_id}")])

        # Кнопка назад всегда
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="mod_tickets")])

        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def reply_to_ticket(ticket_id: int) -> InlineKeyboardMarkup:
        """Клавиатура для ответа на тикет"""
        keyboard = [
            [InlineKeyboardButton(text="Отмена", callback_data=f"mod_ticket_{ticket_id}")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def after_reply(ticket_id: int) -> InlineKeyboardMarkup:
        """Клавиатура после отправки ответа"""
        keyboard = [
            [InlineKeyboardButton(text="➕ Новый ответ", callback_data=f"mod_reply_{ticket_id}")],
            [InlineKeyboardButton(text="📋 Все тикеты", callback_data="mod_tickets")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def _format_time_ago(created_at) -> str:
        """Форматирование времени создания тикета"""
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - created_at
        
        if diff.total_seconds() < 3600:  # меньше часа
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}мин"
        elif diff.total_seconds() < 86400:  # меньше дня
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}ч"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days}д"
