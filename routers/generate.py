"""Image generation router."""
import os
import time
import aiohttp
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form
from pydantic import BaseModel, HttpUrl
from typing import Optional, Union
from services.ai_provider import get_ai_provider
from services.logger import logger
from utils.http_client import http_client


router = APIRouter(prefix="/api/v1", tags=["inference"])


class GenerateRequest(BaseModel):
    """Request model for image generation (JSON with URLs)."""
    user_id: str
    api_key: str
    catalog_id: str
    user_image_url: HttpUrl
    catalog_image_url: HttpUrl


class GenerateResponse(BaseModel):
    """Response model for image generation."""
    status: str
    image_url: Optional[str] = None
    latency_ms: float


async def download_image(url: str) -> bytes:
    """Download image from URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            else:
                raise Exception(f"Failed to download image from {url}: {response.status}")


async def read_file_to_bytes(file_path: str) -> bytes:
    """Read local file to bytes."""
    if not os.path.exists(file_path):
        raise Exception(f"File not found: {file_path}")
    with open(file_path, "rb") as f:
        return f.read()


async def get_image_data(source: Union[str, UploadFile, bytes]) -> bytes:
    """Get image data from URL, file path, UploadFile, or bytes."""
    if isinstance(source, bytes):
        return source
    elif isinstance(source, UploadFile):
        return await source.read()
    elif isinstance(source, str):
        # Check if it's a URL or file path
        if source.startswith(("http://", "https://")):
            return await download_image(source)
        else:
            # Local file path
            return await read_file_to_bytes(source)
    else:
        raise Exception(f"Unsupported image source type: {type(source)}")


async def save_image(image_url_or_data: str, filename: str) -> str:
    """Download and save image to media directory. Handles URLs and base64 data URLs."""
    import base64
    os.makedirs("media", exist_ok=True)
    filepath = os.path.join("media", filename)
    
    # Handle base64 data URL (from Gemini/Imagen)
    if image_url_or_data.startswith("data:image"):
        header, encoded = image_url_or_data.split(",", 1)
        image_data = base64.b64decode(encoded)
        with open(filepath, "wb") as f:
            f.write(image_data)
        return filepath
    
    # Handle regular URL
    image_data = await download_image(image_url_or_data)
    with open(filepath, "wb") as f:
        f.write(image_data)
    
    return filepath


@router.post("/create-image", response_model=GenerateResponse)
async def create_image(
    user_id: str = Form(...),
    api_key: str = Form(...),
    catalog_id: str = Form(...),
    user_image: Optional[UploadFile] = File(None),
    catalog_image: Optional[UploadFile] = File(None),
    user_image_url: Optional[str] = Form(None),
    catalog_image_url: Optional[str] = Form(None)
):
    """Generate virtual try-on image. Accepts file uploads or URLs."""
    start_time = time.time()
    ai_provider_name = os.getenv("AI_PROVIDER", "openai")
    
    try:
        # Get image data from files or URLs
        if user_image:
            user_img_data = await get_image_data(user_image)
            user_img_source = "uploaded_file"
        elif user_image_url:
            user_img_data = await get_image_data(user_image_url)
            user_img_source = user_image_url
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either user_image file or user_image_url must be provided"
            )
        
        if catalog_image:
            catalog_img_data = await get_image_data(catalog_image)
            catalog_img_source = "uploaded_file"
        elif catalog_image_url:
            catalog_img_data = await get_image_data(catalog_image_url)
            catalog_img_source = catalog_image_url
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either catalog_image file or catalog_image_url must be provided"
            )
        
        # Step 1: Verify authentication
        try:
            auth_result = await http_client.verify_auth(user_id, api_key)
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"Backend connection error during auth: {str(e)}"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, error_msg)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to verify authentication. Backend may be unavailable: {str(e)}"
            )
        
        if auth_result.get("status") == 401 or auth_result.get("error") == "Unauthorized":
            latency_ms = (time.time() - start_time) * 1000
            error_detail = auth_result.get("detail") or auth_result.get("message") or "Invalid user_id or api_key"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, f"Unauthorized: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {error_detail}"
            )
        
        # Step 2: Check credits
        try:
            credits_result = await http_client.check_credits(user_id)
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"Backend connection error during credit check: {str(e)}"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, error_msg)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to check credits. Backend may be unavailable: {str(e)}"
            )
        
        if credits_result.get("status") == 403 or credits_result.get("error") == "Forbidden":
            latency_ms = (time.time() - start_time) * 1000
            error_detail = credits_result.get("detail") or credits_result.get("message") or "Insufficient credits"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, f"Insufficient credits: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient credits: {error_detail}"
            )
        
        if not credits_result.get("has_credits", False):
            latency_ms = (time.time() - start_time) * 1000
            error_detail = credits_result.get("detail") or credits_result.get("message") or "No credits available"
            available_credits = credits_result.get("available_credits", "unknown")
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, f"No credits: {error_detail} (available: {available_credits})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient credits: {error_detail}. Available credits: {available_credits}"
            )
        
        # Step 3: Save uploaded images temporarily and generate
        try:
            # Save images to temp files for provider
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as tmp_user:
                tmp_user.write(user_img_data)
                tmp_user_path = tmp_user.name
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as tmp_catalog:
                tmp_catalog.write(catalog_img_data)
                tmp_catalog_path = tmp_catalog.name
            
            try:
                ai_provider = get_ai_provider()
                generated_image_url = await ai_provider.generate_image(
                    tmp_user_path,
                    tmp_catalog_path
                )
            finally:
                # Clean up temp files
                try:
                    os.unlink(tmp_user_path)
                    os.unlink(tmp_catalog_path)
                except:
                    pass
        except ValueError as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"Configuration error: {str(e)}"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI provider configuration error: {str(e)}. Please check environment variables."
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"Image generation failed: {str(e)}"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Image generation failed: {str(e)}"
            )
        
        # Step 4: Save image locally
        try:
            filename = f"{user_id}_{catalog_id}_{int(time.time())}.png"
            local_image_path = await save_image(generated_image_url, filename)
            image_url = f"/media/{filename}"
        except aiohttp.ClientError as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"Network error downloading image: {str(e)}"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, error_msg)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to download generated image: {str(e)}"
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"Image save failed: {str(e)}"
            logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save image: {str(e)}"
            )
        
        # Step 5: Send webhook to backend
        latency_ms = (time.time() - start_time) * 1000
        try:
            await http_client.send_webhook(
                user_id=user_id,
                used_credits=1,
                catalog_id=catalog_id,
                image_url=image_url,
                latency_ms=latency_ms
            )
        except Exception as e:
            # Log webhook failure but don't fail the request
            logger.log_request(user_id, catalog_id, "warning", latency_ms, ai_provider_name, f"Webhook failed: {str(e)}")
        
        # Step 6: Log success and return response
        logger.log_request(user_id, catalog_id, "success", latency_ms, ai_provider_name)
        
        return GenerateResponse(
            status="success",
            image_url=image_url,
            latency_ms=latency_ms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_type = type(e).__name__
        error_msg = f"Unexpected error ({error_type}): {str(e)}"
        logger.log_request(user_id, catalog_id, "error", latency_ms, ai_provider_name, error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

