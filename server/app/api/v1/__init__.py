from fastapi import APIRouter

from . import assets, auth, chat, documents, health, insights, jobs, users

api_router = APIRouter()
for module in (health, auth, users, documents, jobs, chat, assets, insights):
    api_router.include_router(module.router)
