from fastapi import APIRouter
from app.api import (
    patients, documents, agent, summary, learning, system, debug, analytics,
    review, search, timeline,
)

api_router = APIRouter()
api_router.include_router(patients.router)
api_router.include_router(documents.router)
api_router.include_router(agent.router)
api_router.include_router(summary.router)
api_router.include_router(learning.router)
api_router.include_router(system.router)
api_router.include_router(debug.router)
api_router.include_router(analytics.router)
api_router.include_router(review.router)
api_router.include_router(search.router)
api_router.include_router(timeline.router)

