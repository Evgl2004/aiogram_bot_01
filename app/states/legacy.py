"""
Состояния для процесса апгрейда пользователей из старого бота.
"""

from aiogram.fsm.state import State, StatesGroup


class LegacyUpgrade(StatesGroup):
    """
    Группа состояний для приведения данных устаревшие-пользователей в порядок.
    """

    waiting_for_rules_consent = State()             # ожидание согласия с правилами
    waiting_for_field = State()                     # ожидание ввода очередного поля
    waiting_for_review = State()                    # показ анкеты, ожидание подтверждения
    waiting_for_edit_choice = State()               # выбор поля для редактирования
    waiting_for_edit_field = State()                # редактирование конкретного поля
    waiting_for_notifications_consent = State()     # согласие на уведомления
