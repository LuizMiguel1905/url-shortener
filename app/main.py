from fastapi import FastAPI

from app.routes import router

# O schema do banco é gerenciado pelo Alembic (`alembic upgrade head`), não pelo app.
app = FastAPI(title="Encurtador de URL")
app.include_router(router)
