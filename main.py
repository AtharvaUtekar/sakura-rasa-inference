"""FastAPI inference server entry point."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from routers import generate
from utils.throttle import ThrottleMiddleware


# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Sakura Rasa Inference Server",
    description="AI-based virtual try-on image generation service with modular AI providers (OpenAI, Gemini, Sora, Stability)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Throttling middleware
requests_per_minute = int(os.getenv("THROTTLE_RPM", "10"))
app.add_middleware(ThrottleMiddleware, requests_per_minute=requests_per_minute)

# Include routers
app.include_router(generate.router)

# Mount media directory for serving generated images
os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "status": "ok",
        "service": os.getenv("SERVICE_NAME", "sakura-rasa-inference"),
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )

