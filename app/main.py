from fastapi import FastAPI

from app.api.routes.certificates import router as certificates_router

app = FastAPI(title="Bulk Certificate Generator")
app.include_router(certificates_router)
