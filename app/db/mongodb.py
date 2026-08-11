import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


db = MongoDB()


async def connect_to_mongo():
    """Connect to MongoDB and ensure indexes exist."""
    logger.info("Connecting to MongoDB at %s...", settings.MONGODB_URI)
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    db.db = db.client[settings.MONGODB_DB_NAME]

    # Create indexes for optimal query performance
    try:
        messages_col = db.db.get_collection("messages")
        await messages_col.create_index(
            [("conversation_id", 1), ("timestamp", 1)],
            name="idx_conversation_timestamp",
        )

        conversations_col = db.db.get_collection("conversations")
        await conversations_col.create_index(
            [("updated_at", -1)],
            name="idx_updated_at",
        )

        logger.info("MongoDB connection established and indexes verified.")
    except Exception as e:
        logger.warning("MongoDB index creation notice: %s", e)


async def close_mongo_connection():
    """Close MongoDB connection on application shutdown."""
    if db.client:
        logger.info("Closing MongoDB connection...")
        db.client.close()
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    """Dependency / Helper to retrieve active AsyncIOMotorDatabase instance."""
    if db.db is None:
        raise RuntimeError("Database connection has not been initialized.")
    return db.db
