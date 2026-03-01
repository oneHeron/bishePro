from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.public import router as public_router
from app.api.runs import router as runs_router
from app.db import init_db
from app.services.plugin_loader import load_builtin_plugins

app = FastAPI(title="Community Detection Integration Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


load_builtin_plugins()
init_db()


@app.get("/")
def health() -> dict:
    return {"message": "backend is running"}


app.include_router(public_router)
app.include_router(auth_router)
app.include_router(runs_router)
