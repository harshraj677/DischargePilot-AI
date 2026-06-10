from fastapi import APIRouter
from app.api import patients, documents, agent, summary, learning, system

api_router = APIRouter()
api_router.include_router(patients.router)
api_router.include_router(documents.router)
api_router.include_router(agent.router)
api_router.include_router(summary.router)
api_router.include_router(learning.router)
api_router.include_router(system.router)
