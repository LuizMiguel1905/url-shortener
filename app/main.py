import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.redirects import flush_pending_clicks_forever, flush_without_raising
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    flusher = asyncio.create_task(flush_pending_clicks_forever())
    yield
    flusher.cancel()
    with suppress(asyncio.CancelledError):
        await flusher
    await flush_without_raising()


app = FastAPI(title="Encurtador de URL", lifespan=lifespan)
app.include_router(router)
