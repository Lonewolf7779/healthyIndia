from fastapi import APIRouter

from app.api.v1.endpoints import health, ingredients, nutrition

api_v1_router = APIRouter()

# Register endpoint routers
api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(nutrition.router, prefix="/nutrition", tags=["Nutrition"])
api_v1_router.include_router(ingredients.router, prefix="/ingredients", tags=["Ingredients"])
