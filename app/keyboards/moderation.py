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
    def tickets_list(tickets: List[Ticket]) -> InlineKeyboardMarkup:
        """Список тикетов"""
        keyboard = []
        
        for ticket in tickets:
            # Определяем эмодзи для статуса
            status_emoji = "🆕" if ticket.status == "open" else "🔄"
            
            # Формируем текст кнопки
            username = ticket.user_username or ticket.user_first_name or f"ID:{ticket.user_id}"
            time_ago = ModerationKeyboard._format_time_ago(ticket.created_at)
            button_text = f"{status_emoji} #{ticket.id} от {username} ({time_ago})"
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"mod_ticket_{ticket.id}"
                )
            ])
        
        # Кнопка назад
        keyboard.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="mod_main")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def ticket_details(ticket_id: int) -> InlineKeyboardMarkup:
        """Детали тикета"""
        keyboard = [
            [InlineKeyboardButton(text="📩 Ответить", callback_data=f"mod_reply_{ticket_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="mod_tickets")]
        ]
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
