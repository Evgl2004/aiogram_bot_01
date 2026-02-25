"""
Модели базы данных

Этот файл содержит описание структуры таблиц в базе данных.
Каждый класс — это отдельная таблица, а атрибуты класса — колонки в таблице.
SQLAlchemy автоматически создаст таблицы по этим описаниям при первом запуске
(или применит миграции, если таблицы уже существуют, но структура изменилась).
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import BigInteger, DateTime, String, Boolean, Integer, Text, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей

    От него наследуются все классы-таблицы. Служит для того, чтобы SQLAlchemy
    могла обнаружить все модели и создать соответствующие таблицы.
    """
    pass


class User(Base):
    """
    Модель пользователя Telegram

    Хранит информацию о каждом пользователе, который взаимодействовал с ботом.
    Основные поля (username, first_name и т.д.) заполняются автоматически
    при первом обращении пользователя к боту. Дополнительные поля (phone_number,
    full_name и др.) заполняются в процессе регистрации.
    """
    
    __tablename__ = "users"

    # --- Основные данные пользователя (заполняются автоматически) ---
    """
    Telegram ID пользователя.
    Уникальный идентификатор, который Telegram присваивает каждому аккаунту.
    Используется как первичный ключ.
    """
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    """
    Username пользователя в Telegram (то, что после @).
    Может отсутствовать (nullable=True), если пользователь не установил username.
    """
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    """Имя пользователя, указанное в Telegram."""
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    """Фамилия пользователя, указанная в Telegram (может отсутствовать)."""
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    """
    Признак активности пользователя.
    True — пользователь активен (по умолчанию). False — заблокировал бота или помечен как неактивный.
    Используется для статистики и рассылок.
    """
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    """
    Дата и время первого обращения пользователя к боту.
    Устанавливается автоматически при создании записи.
    """
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    """
    Дата и время последнего обновления записи.
    Автоматически обновляется при любом изменении данных пользователя.
    """
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Добавленные поля для регистрации и согласий ---

    """
    Согласие с условиями оферты и на обработку персональных данных.
    True — пользователь принял правила, False — ещё не принял (по умолчанию).
    Без этого согласия нельзя продолжать регистрацию.
    """
    rules_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    """
    Отдельное согласие на получение информационных и рекламных уведомлений.
    Требуется по закону о рекламе и персональных данных.
    True — согласен получать уведомления, False — не согласен.
    """
    notifications_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    """
    Признак завершения полной регистрации.
    True — все обязательные поля анкеты заполнены, пользователь может пользоваться основным функционалом.
    False — регистрация ещё не завершена (по умолчанию).
    """
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    """
    Номер телефона пользователя.
    Получается через специальную кнопку Telegram «Поделиться контактом».
    Хранится в формате строки (например, +71234567890).
    """
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    """
    Полное имя пользователя, которое он введёт сам.
    Может отличаться от first_name/last_name (например, Иван Петров).
    """
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    """
    Предпочитаемое Имя (первое слово из full_name, для обращений)
    """
    preferred_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    """
    Пол пользователя.
    Ожидаемые значения: "male" (мужской) или "female" (женский).
    Запрашивается у пользователя через кнопки.
    """
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    """
    Дата рождения пользователя.
    Хранится в формате ДД.ММ.ГГГГ как строка для простоты.
    Можно при необходимости преобразовывать в объект date.
    """
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    """Адрес электронной почты пользователя."""
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # --------------------------------------
    
    def __repr__(self) -> str:
        """
        Строковое представление объекта пользователя.
        Используется для отладки.
        """
        return f"<User(id={self.id}, username={self.username})>"


class BotStats(Base):
    """
    Модель статистики бота

    Хранит общую информацию о работе бота: количество пользователей,
    время последнего перезапуска и т.п. Обычно содержит одну запись,
    которая обновляется при старте бота и при изменениях статистики.
    """
    
    __tablename__ = "bot_stats"

    """Внутренний идентификатор записи статистики."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    """Общее количество пользователей, когда-либо взаимодействовавших с ботом."""
    total_users: Mapped[int] = mapped_column(Integer, default=0)

    """Количество активных пользователей (например, за последние сутки)."""
    active_users: Mapped[int] = mapped_column(Integer, default=0)

    """Дата и время последнего перезапуска бота (автоматически при создании записи)."""
    last_restart: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    """
    Статус бота.
    Может использоваться для различных целей (например, "active", "maintenance").
    """
    status: Mapped[str] = mapped_column(String(50), default="active")

    """Дата и время создания записи статистики (обычно первый запуск бота)."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self) -> str:
        return f"<BotStats(total_users={self.total_users}, status={self.status})>"


class MigrationHistory(Base):
    """
    Модель для отслеживания применённых миграций базы данных.

    Используется системой автоматических миграций шаблона.
    Каждый раз, когда применяется новая миграция, в эту таблицу добавляется запись.
    Это позволяет знать, какие миграции уже выполнены, и не применять их повторно.
    """

    __tablename__ = "migration_history"

    """Внутренний идентификатор записи о миграции."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    """
    Версия миграции (обычно дата и номер, например "20241201_000001").
    Должна быть уникальной.
    """
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    """Краткое название миграции (например, "InitialTablesMigration")."""
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    """Описание миграции (что именно она делает)."""
    description: Mapped[str] = mapped_column(Text, nullable=True)

    """Дата и время применения миграции."""
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    """Время выполнения миграции в секундах (для анализа производительности)."""
    execution_time: Mapped[Optional[float]] = mapped_column(nullable=True)  # время выполнения в секундах
    
    def __repr__(self) -> str:
        return f"<MigrationHistory(version={self.version}, name={self.name})>"
