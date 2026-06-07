# Python Examples

## Type Hints with Pydantic

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class User(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True

    class Config:
        frozen = True  # Immutable instances

def get_user(user_id: int) -> Optional[User]:
    """Fetch user by ID with proper type hints."""
    ...
```

## Async Context Manager

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

@asynccontextmanager
async def database_connection(url: str) -> AsyncGenerator[Connection, None]:
    """Async context manager for database connections."""
    conn = await connect(url)
    try:
        yield conn
    finally:
        await conn.close()

async def query_users():
    async with database_connection("postgresql://...") as conn:
        return await conn.fetch("SELECT * FROM users")
```

## Decorator Pattern

```python
from functools import wraps
from typing import Callable, Any
import logging

def retry(max_attempts: int = 3, delay: float = 1.0) -> Callable:
    """Decorator to retry function calls on failure."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    logging.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay)
            raise last_error
        return wrapper
    return decorator

@retry(max_attempts=3, delay=0.5)
async def fetch_data(url: str) -> dict:
    """Fetch data with automatic retry."""
    ...
```

## Repository Pattern

```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List

T = TypeVar("T")

class Repository(ABC, Generic[T]):
    """Abstract repository interface."""

    @abstractmethod
    async def get(self, id: int) -> Optional[T]:
        ...

    @abstractmethod
    async def list(self) -> List[T]:
        ...

    @abstractmethod
    async def create(self, entity: T) -> T:
        ...

    @abstractmethod
    async def update(self, entity: T) -> T:
        ...

    @abstractmethod
    async def delete(self, id: int) -> bool:
        ...

class UserRepository(Repository[User]):
    """Concrete repository for User entities."""

    def __init__(self, db: Database):
        self.db = db

    async def get(self, id: int) -> Optional[User]:
        row = await self.db.fetchrow("SELECT * FROM users WHERE id = $1", id)
        return User(**row) if row else None
```
