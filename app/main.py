from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="Encurtador de URL")
app.include_router(router)
