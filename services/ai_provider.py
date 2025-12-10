"""Modular AI provider interface for image generation."""
import os
import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Optional
from openai import OpenAI, OpenAIError
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core import exceptions as google_exceptions


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    async def generate_image(
        self,
        user_img_url: str,
        catalog_img_url: str,
        prompt: Optional[str] = None
    ) -> str:
        """Generate virtual try-on image."""
        pass


class OpenAIProvider(AIProvider):
    """OpenAI DALL-E provider for image generation."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.client = OpenAI(api_key=api_key)
        self.model = "dall-e-3"
        self.size = "1024x1024"
        self.quality = "hd"
    
    async def generate_image(
        self,
        user_img_url: str,
        catalog_img_url: str,
        prompt: Optional[str] = None
    ) -> str:
        """Generate virtual try-on image using OpenAI DALL-E."""
        if not prompt:
            prompt = (
                "Generate a high-fidelity virtual try-on image where the person "
                "from the user image is wearing the clothing item from the catalog image. "
                "Maintain the user's facial features, body proportions, and pose while "
                "accurately applying the catalog item. Ensure realistic lighting, shadows, "
                "and fabric texture. Preserve catalog item details (patterns, colors, design) "
                "and the user's natural appearance. The result should be photorealistic and "
                "seamlessly integrated."
            )
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size=self.size,
                    quality=self.quality,
                    n=1
                )
            )
            
            if response.data and len(response.data) > 0:
                return response.data[0].url
            else:
                raise Exception("No image URL returned from OpenAI")
        
        except OpenAIError as e:
            raise Exception(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Image generation error: {str(e)}")


class GeminiProvider(AIProvider):
    """Google Gemini provider for image generation using Imagen API."""
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        genai.configure(api_key=api_key)
        self.api_key = api_key
        self.model = "gemini-2.5-flash-image"
        self.prompt_template = (
            "take the person from the first reference image and the garment and the setting "
            "from the second image, virtual try on should match the model's body. catalogue shoot. "
            "4k. photorealistic. new shot and visual. three quarter angle shot"
        )
    
    async def _download_image(self, url_or_path: str) -> bytes:
        """Download image from URL or read from local file path."""
        # Check if it's a local file path
        if os.path.exists(url_or_path) and not url_or_path.startswith(("http://", "https://")):
            try:
                with open(url_or_path, "rb") as f:
                    return f.read()
            except Exception as e:
                raise Exception(f"Failed to read local file {url_or_path}: {str(e)}")
        
        # Otherwise, treat as URL
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url_or_path, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.read()
                    elif response.status == 404:
                        raise Exception(f"Image not found at URL: {url_or_path}")
                    elif response.status == 403:
                        raise Exception(f"Access forbidden for image URL: {url_or_path}")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to download image from {url_or_path}: HTTP {response.status} - {error_text[:100]}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error downloading image from {url_or_path}: {str(e)}")
        except asyncio.TimeoutError:
            raise Exception(f"Timeout downloading image from {url_or_path}")
        except Exception as e:
            raise Exception(f"Error downloading image from {url_or_path}: {str(e)}")
    
    async def generate_image(
        self,
        user_img_url: str,
        catalog_img_url: str,
        prompt: Optional[str] = None
    ) -> str:
        """Generate virtual try-on image using Google Gemini/Imagen."""
        try:
            # Download images with detailed error handling
            try:
                user_img_data = await self._download_image(user_img_url)
            except Exception as e:
                raise Exception(f"Failed to download user image from {user_img_url}: {str(e)}")
            
            try:
                catalog_img_data = await self._download_image(catalog_img_url)
            except Exception as e:
                raise Exception(f"Failed to download catalog image from {catalog_img_url}: {str(e)}")
            
            final_prompt = prompt or self.prompt_template
            
            loop = asyncio.get_event_loop()
            
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            try:
                model = genai.GenerativeModel(
                    model_name=self.model,
                    safety_settings=safety_settings
                )
            except Exception as e:
                raise Exception(f"Failed to initialize Gemini model '{self.model}': {str(e)}. Check if model name is correct.")
            
            import PIL.Image
            import io
            
            try:
                user_img = PIL.Image.open(io.BytesIO(user_img_data))
                catalog_img = PIL.Image.open(io.BytesIO(catalog_img_data))
            except Exception as e:
                raise Exception(f"Failed to process images: {str(e)}. Ensure URLs point to valid image files.")
            
            # Use Gemini to enhance prompt with image context
            analysis_prompt = (
                f"{final_prompt}\n\n"
                "First image shows the person/model. Second image shows the garment and setting. "
                "Create a detailed prompt for generating the virtual try-on result."
            )
            
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: model.generate_content([analysis_prompt, user_img, catalog_img])
                )
            except google_exceptions.GoogleAPIError as e:
                raise Exception(f"Gemini API error: {str(e)}. Check your API key and quota.")
            except Exception as e:
                raise Exception(f"Error calling Gemini API: {str(e)}")
            
            enhanced_prompt = response.text if hasattr(response, 'text') and response.text else final_prompt
            
            # Generate image using Imagen API
            try:
                return await self._generate_with_imagen(user_img_data, catalog_img_data, enhanced_prompt)
            except Exception as e:
                raise Exception(f"Image generation failed: {str(e)}")
            
        except Exception as e:
            # Re-raise with context if not already wrapped
            error_str = str(e)
            if "Failed to" in error_str or "Error" in error_str or "API error" in error_str:
                raise
            raise Exception(f"Gemini image generation error: {error_str}")
    
    async def _generate_with_imagen(
        self, user_img: bytes, catalog_img: bytes, prompt: str
    ) -> str:
        """Generate image using Imagen API via REST."""
        project_id = os.getenv("GOOGLE_PROJECT_ID")
        location = os.getenv("GOOGLE_LOCATION", "us-central1")
        
        # Try to use Imagen API if project ID is available
        if project_id:
            try:
                access_token = await self._get_access_token()
                url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/imagegeneration@006:predict"
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "instances": [{
                        "prompt": prompt,
                        "number_of_images": 1
                    }],
                    "parameters": {
                        "sampleCount": 1,
                        "aspectRatio": "1:1"
                    }
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as response:
                        if response.status == 200:
                            result = await response.json()
                            if "predictions" in result and result["predictions"]:
                                img_data = result["predictions"][0].get("bytesBase64Encoded", "")
                                if img_data:
                                    return f"data:image/png;base64,{img_data}"
                        error_text = await response.text()
                        raise Exception(f"Imagen API error: {response.status} - {error_text}")
            except Exception as e:
                # If Imagen fails, fall through to alternative method
                pass
        
        # Alternative: Use Gemini API with image generation via REST API
        # Note: This uses Gemini's capabilities to create image generation requests
        return await self._generate_via_gemini_rest(prompt, user_img, catalog_img)
    
    async def _generate_via_gemini_rest(
        self, prompt: str, user_img: bytes, catalog_img: bytes
    ) -> str:
        """Generate image using alternative methods when Imagen API is not available."""
        # Note: Gemini API key alone cannot generate images directly
        # Imagen API requires Vertex AI project setup
        # For now, we'll use Gemini to create the best possible prompt
        # and provide guidance for setting up Imagen API
        
        raise Exception(
            "Image generation requires Imagen API access. "
            "Please set GOOGLE_PROJECT_ID in .env for Vertex AI Imagen API, "
            "or configure a Google Cloud project with Imagen API enabled. "
            "The Gemini API key is used for image analysis and prompt enhancement, "
            "but image generation requires Imagen API which needs a project ID."
        )
    
    async def _get_access_token(self) -> str:
        """Get access token for Vertex AI."""
        # Try service account first
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if service_account_path and os.path.exists(service_account_path):
            try:
                from google.auth import default
                from google.auth.transport.requests import Request
                credentials, _ = default()
                credentials.refresh(Request())
                return credentials.token
            except Exception:
                pass
        
        # Fallback: Try to use API key (may work for some endpoints)
        return self.api_key


class SoraProvider(AIProvider):
    """Sora provider placeholder for future implementation."""
    
    async def generate_image(
        self,
        user_img_url: str,
        catalog_img_url: str,
        prompt: Optional[str] = None
    ) -> str:
        """Placeholder for Sora implementation."""
        raise NotImplementedError("Sora provider not yet implemented")


class StabilityProvider(AIProvider):
    """Stability AI provider placeholder for future implementation."""
    
    async def generate_image(
        self,
        user_img_url: str,
        catalog_img_url: str,
        prompt: Optional[str] = None
    ) -> str:
        """Placeholder for Stability AI implementation."""
        raise NotImplementedError("Stability AI provider not yet implemented")


def get_ai_provider() -> AIProvider:
    """Get AI provider based on environment configuration."""
    provider_name = os.getenv("AI_PROVIDER", "openai").lower()
    
    providers = {
        "openai": OpenAIProvider,
        "sora": SoraProvider,
        "gemini": GeminiProvider,
        "stability": StabilityProvider
    }
    
    provider_class = providers.get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown AI provider: {provider_name}")
    
    return provider_class()
