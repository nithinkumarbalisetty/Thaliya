from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers import auth, ecare, georgetown, chronic_care_bridge, anarcare, otp_router
from app.core.config import settings
from app.core.database import db


# Create FastAPI instance
app = FastAPI(
    title="Thaliya Healthcare API Gateway",
    description="API Gateway for E-Care, GeorgeTown, ChronicCareBridge, and Anarcare services",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(otp_router.router, tags=["OTP Authentication"])
app.include_router(ecare.router, prefix="/api/v1/ecare", tags=["E-Care"])
app.include_router(georgetown.router, prefix="/api/v1/georgetown", tags=["GeorgeTown"])
app.include_router(chronic_care_bridge.router, prefix="/api/v1/chronic-care-bridge", tags=["ChronicCareBridge"])
app.include_router(anarcare.router, prefix="/api/v1/anarcare", tags=["Anarcare"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Thaliya Healthcare API Gateway",
        "version": "1.0.0",
        "services": ["E-Care", "GeorgeTown", "ChronicCareBridge", "Anarcare"]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Thaliya"}

# Database connection events
@app.on_event("startup")
async def startup():
    await db.connect()
    print("Database connected successfully")

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()
    print("Database disconnected")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
