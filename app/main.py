from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.routes.health import router as health_router
from app.auth.middleware import ApiKeyAuthMiddleware


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(title="ZenRows Device Profiles API")
    app.add_middleware(ApiKeyAuthMiddleware)
    app.include_router(health_router)
    return app


app = create_app()
