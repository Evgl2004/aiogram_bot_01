"""
Add all missing user fields to match current model and create tickets tables
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class AddAllMissingUserFieldsAndTicketsMigration(Migration):
    """
    Добавляет все поля, которые присутствуют в модели User,
    но могут отсутствовать в таблице users, и создаёт таблицы для системы тикетов.
    Миграция безопасна для повторного применения (использует IF NOT EXISTS).
    """

    def get_version(self) -> str:
        # Версию можно оставить прежней или изменить, если это новая миграция
        return "20260301_164757"

    def get_description(self) -> str:
        return "Add all missing user fields and create tickets tables"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        # Проверяем существование таблицы users – если её нет, миграцию применять бессмысленно
        result = await connection.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
        )
        return result.scalar()

    async def upgrade(self, connection: AsyncConnection) -> None:
        """
        Добавляем поля пользователя и создаём таблицы tickets / ticket_messages.
        """
        # --- Часть 1: добавление полей пользователя ---
        logger.info("Adding missing user fields...")

        # Поля согласий и legacy
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS rules_accepted BOOLEAN NOT NULL DEFAULT FALSE
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS rules_accepted_at TIMESTAMPTZ
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS notifications_allowed BOOLEAN NOT NULL DEFAULT FALSE
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS notifications_allowed_at TIMESTAMPTZ
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_legacy BOOLEAN NOT NULL DEFAULT FALSE
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_registered BOOLEAN NOT NULL DEFAULT FALSE
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_moderator BOOLEAN NOT NULL DEFAULT FALSE
        """))

        # Личные данные
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20)
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS first_name_input VARCHAR(255)
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS last_name_input VARCHAR(255)
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS gender VARCHAR(10)
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS birth_date DATE
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS email VARCHAR(255)
        """))

        logger.info("✅ User fields added (if missing)")

        # --- Часть 2: создание таблиц тикетов ---
        logger.info("Creating tickets tables...")

        # Таблица tickets
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                user_username VARCHAR(255),
                user_first_name VARCHAR(255),
                message TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'open',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                first_response_at TIMESTAMP WITH TIME ZONE NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))

        # Индексы для tickets
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
        """))

        # Таблица ticket_messages
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id SERIAL PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                sender_type VARCHAR(10) NOT NULL,
                sender_id BIGINT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))

        # Индексы для ticket_messages
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages(ticket_id);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ticket_messages_sender_type ON ticket_messages(sender_type);
        """))
        await connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ticket_messages_created_at ON ticket_messages(created_at);
        """))

        # Внешний ключ (с проверкой существования, т.к. IF NOT EXISTS для ограничений не поддерживается)
        fk_check = await connection.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_ticket_messages_ticket_id'
                  AND table_name = 'ticket_messages'
            )
        """))
        if not fk_check.scalar():
            await connection.execute(text("""
                ALTER TABLE ticket_messages
                ADD CONSTRAINT fk_ticket_messages_ticket_id
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            """))
            logger.info("Foreign key fk_ticket_messages_ticket_id added")
        else:
            logger.info("Foreign key fk_ticket_messages_ticket_id already exists")

        logger.info("✅ Tickets tables created (if missing)")

    async def downgrade(self, connection: AsyncConnection) -> None:
        """
        Откат миграции: удаляем таблицы тикетов, затем удаляем добавленные поля из users.
        """
        # Сначала таблицы тикетов (из-за внешних ключей)
        logger.info("Dropping tickets tables...")
        await connection.execute(text("DROP TABLE IF EXISTS ticket_messages CASCADE;"))
        await connection.execute(text("DROP TABLE IF EXISTS tickets CASCADE;"))
        logger.info("✅ Tickets tables dropped")

        # Затем поля пользователя
        logger.info("Dropping user fields...")
        fields_to_drop = [
            'rules_accepted', 'rules_accepted_at', 'notifications_allowed',
            'notifications_allowed_at', 'is_legacy', 'is_registered', 'is_moderator'
            'phone_number', 'first_name_input', 'last_name_input',
            'gender', 'birth_date', 'email'
        ]
        for field in fields_to_drop:
            await connection.execute(text(f"ALTER TABLE users DROP COLUMN IF EXISTS {field}"))
        logger.info("✅ User fields dropped")