"""
Add closed_at column to tickets table
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from loguru import logger

from app.database.migrations.base import Migration


class AddClosedAtToTicketsMigration(Migration):
    """Добавляет колонку closed_at в таблицу tickets, если её нет."""

    def get_version(self) -> str:
        # Используем текущую дату и время, например 20260304_120000
        return "20260304_054237"

    def get_description(self) -> str:
        return "Add closed_at column to tickets table"

    async def check_can_apply(self, connection: AsyncConnection) -> bool:
        # Проверяем существование таблицы tickets
        result = await connection.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tickets')")
        )
        return result.scalar()

    async def upgrade(self, connection: AsyncConnection) -> None:
        logger.info("Adding column closed_at to tickets table...")
        await connection.execute(text("""
            ALTER TABLE tickets
            ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP WITH TIME ZONE
        """))
        logger.info("✅ Column closed_at added (if missing)")

    async def downgrade(self, connection: AsyncConnection) -> None:
        logger.info("Removing column closed_at from tickets table...")
        await connection.execute(text("ALTER TABLE tickets DROP COLUMN IF EXISTS closed_at"))
        logger.info("✅ Column closed_at removed")