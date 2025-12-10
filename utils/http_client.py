"""Async HTTP client for Django backend integration."""
import os
import asyncio
import aiohttp
from typing import Dict, Optional, Any
from aiohttp import ClientError, ClientTimeout


class HTTPClient:
    """Async HTTP client with retry logic and error handling."""
    
    def __init__(self):
        self.base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.timeout = ClientTimeout(total=30)
        self.max_retries = 3
        self.retry_delay = 1
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic and detailed error handling."""
        url = f"{self.base_url}{endpoint}"
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.request(
                        method, url, json=data, headers=default_headers
                    ) as response:
                        response_data = None
                        try:
                            response_data = await response.json()
                        except:
                            response_text = await response.text()
                            response_data = {"detail": response_text} if response_text else {}
                        
                        if response.status == 200:
                            return response_data
                        elif response.status == 401:
                            error_msg = response_data.get("detail", response_data.get("error", "Authentication failed"))
                            return {
                                "error": "Unauthorized",
                                "detail": error_msg,
                                "status": 401,
                                "message": f"Authentication failed: {error_msg}"
                            }
                        elif response.status == 403:
                            error_msg = response_data.get("detail", response_data.get("error", "Access forbidden"))
                            return {
                                "error": "Forbidden",
                                "detail": error_msg,
                                "status": 403,
                                "message": f"Insufficient credits or access denied: {error_msg}"
                            }
                        elif response.status == 404:
                            return {
                                "error": "Not Found",
                                "detail": f"Endpoint not found: {endpoint}",
                                "status": 404,
                                "message": f"Backend endpoint {endpoint} not found"
                            }
                        elif response.status >= 500:
                            error_msg = response_data.get("detail", response_data.get("error", "Server error"))
                            return {
                                "error": "Backend Server Error",
                                "detail": error_msg,
                                "status": response.status,
                                "message": f"Backend server error: {error_msg}"
                            }
                        else:
                            error_msg = response_data.get("detail", response_data.get("error", "Unknown error"))
                            return {
                                "error": f"Backend error ({response.status})",
                                "detail": error_msg,
                                "status": response.status,
                                "message": f"Backend returned error: {error_msg}"
                            }
            except ClientError as e:
                last_error = f"Network error: {str(e)}"
                if attempt == self.max_retries - 1:
                    raise Exception(f"Network error after {self.max_retries} attempts connecting to {url}: {str(e)}")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
            except asyncio.TimeoutError:
                last_error = "Request timeout"
                if attempt == self.max_retries - 1:
                    raise Exception(f"Request timeout after {self.max_retries} attempts for {url}")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
            except Exception as e:
                last_error = str(e)
                if attempt == self.max_retries - 1:
                    raise Exception(f"Request failed after {self.max_retries} attempts for {url}: {str(e)}")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        raise Exception(f"Request failed after all retries: {last_error}")
    
    async def verify_auth(self, user_id: str, api_key: str) -> Dict[str, Any]:
        """Verify user authentication with backend."""
        return await self._request(
            "POST",
            "/api/v1/auth/verify/",
            data={"user_id": user_id, "api_key": api_key}
        )
    
    async def check_credits(self, user_id: str) -> Dict[str, Any]:
        """Check available credits for user."""
        from urllib.parse import urlencode
        params = urlencode({"user_id": user_id})
        return await self._request(
            "GET",
            f"/api/v1/credits/check/?{params}"
        )
    
    async def send_webhook(
        self,
        user_id: str,
        used_credits: int,
        catalog_id: str,
        image_url: str,
        latency_ms: float
    ) -> Dict[str, Any]:
        """Send webhook update to backend."""
        return await self._request(
            "POST",
            "/api/v1/inference/webhook/",
            data={
                "user_id": user_id,
                "used_credits": used_credits,
                "catalog_id": catalog_id,
                "image_url": image_url,
                "latency_ms": latency_ms
            }
        )


http_client = HTTPClient()

