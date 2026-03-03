"""
Состояния для системы тикетов
"""
from aiogram.fsm.state import State, StatesGroup


class TicketStates(StatesGroup):
    """Состояния для работы с тикетами"""
    
    # Состояние ожидания вопроса от пользователя
    waiting_for_question = State()
    
    # Состояние ожидания ответа модератора на тикет
    waiting_for_moderator_reply = State()