import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from src.main import app
from src.config import settings
from src.database import get_db
from src.repository import InventoryRepository

# Use NullPool for isolated per-test event loops
test_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(scope="function")
async def client():
    # Reset seed inventory before each test
    async with TestSessionLocal() as session:
        repo = InventoryRepository(session)
        await repo.reset_seed_data()

    async with ASGITransport(app=app) as transport:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
