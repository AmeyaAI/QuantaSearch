from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router.api import m_router

origins = [
    "*",
]

app = FastAPI(
    title="Doc Search API",
    description="API for uploading and searching similar files",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sub_app = FastAPI()

sub_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sub_app.include_router(m_router)

@sub_app.get("/health", tags=["SYSTEM"])
async def check_api_status():
    """
    Health check endpoint for the API service.
    
    Simple endpoint to verify that the API is running and responsive.
    
    Returns:
        dict: Status response indicating service health
    """
    
    return {"status": "healthy"}


app.mount("/quantasearch/v1", sub_app)