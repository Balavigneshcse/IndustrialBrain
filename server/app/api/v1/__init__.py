from fastapi import APIRouter

from . import auth, chat, documents, health, insights, users

api_router = APIRouter()
for module in (health, auth, users, documents, chat, insights):
    api_router.include_router(module.router)
