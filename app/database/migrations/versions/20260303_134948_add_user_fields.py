"""
Add is_moderator column to users table
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class AddIsModeratorColumnMigration(Migration):
    """Добавляет колонку is_moderator в таблицу users, если её нет."""

    def get_version(self) -> str:
        return "20260303_134948"

    def get_description(self) -> str:
        return "Add is_moderator column to users table"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        # Проверяем существование таблицы users
        result = await connection.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
        )
        return result.scalar()

    async def upgrade(self, connection: AsyncConnection) -> None:
        logger.info("Adding column is_moderator to users table...")
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_moderator BOOLEAN NOT NULL DEFAULT FALSE
        """))
        logger.info("✅ Column is_moderator added (if missing)")

    async def downgrade(self, connection: AsyncConnection) -> None:
        logger.info("Removing column is_moderator from users table...")
        await connection.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_moderator"))
        logger.info("✅ Column is_moderator removed")