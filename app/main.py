from fastapi import FastAPI
from fastapi.openapi.models import APIKey
from dotenv import load_dotenv
from app.api.routes.health import router as health_router
from app.api.routes.device_profiles import router as profiles_router
from app.auth.middleware import ApiKeyAuthMiddleware


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(
        title="ZenRows Device Profiles API",
        version="0.0.1",
        servers=[{"url": "/", "description": "Container default"}],
        swagger_ui_parameters={"persistAuthorization": True},
    )
    app.add_middleware(ApiKeyAuthMiddleware)
    app.include_router(health_router)
    app.include_router(profiles_router)
    # Add API Key auth to OpenAPI so Swagger 'Authorize' can send X-API-Key
    # Note: Middleware still enforces it server-side.
    if app.openapi_schema is None:
        schema = app.openapi()
    else:
        schema = app.openapi_schema
    comp = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    comp["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return app


app = create_app()
