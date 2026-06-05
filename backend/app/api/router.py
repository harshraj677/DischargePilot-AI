from fastapi import APIRouter
from app.api import patients, documents, agent

api_router = APIRouter()
api_router.include_router(patients.router)
api_router.include_router(documents.router)
api_router.include_router(agent.router)
