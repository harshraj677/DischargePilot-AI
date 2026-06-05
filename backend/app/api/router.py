from fastapi import APIRouter
from app.api import patients, documents

api_router = APIRouter()
api_router.include_router(patients.router)
api_router.include_router(documents.router)
