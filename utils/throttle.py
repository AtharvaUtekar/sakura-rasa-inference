"""Rate limiting and throttling middleware."""
import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple


class ThrottleMiddleware(BaseHTTPMiddleware):
    """Throttle requests per user/IP."""
    
    def __init__(self, app, requests_per_minute: int = 10):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 60
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next):
        # Cleanup old entries periodically
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Get client identifier
        client_id = request.client.host if request.client else "unknown"
        user_id = request.headers.get("X-User-ID") or client_id
        
        # Check rate limit
        if self._is_rate_limited(user_id, current_time):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute."
            )
        
        # Record request
        self.requests[user_id].append(current_time)
        
        # Process request
        response = await call_next(request)
        return response
    
    def _is_rate_limited(self, user_id: str, current_time: float) -> bool:
        """Check if user has exceeded rate limit."""
        minute_ago = current_time - 60
        user_requests = [req_time for req_time in self.requests[user_id] if req_time > minute_ago]
        self.requests[user_id] = user_requests
        return len(user_requests) >= self.requests_per_minute
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove entries older than 1 minute."""
        minute_ago = current_time - 60
        for user_id in list(self.requests.keys()):
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id] 
                if req_time > minute_ago
            ]
            if not self.requests[user_id]:
                del self.requests[user_id]

