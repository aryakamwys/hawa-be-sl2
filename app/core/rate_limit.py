"""
Rate Limiting Middleware for HAWA Backend
Handles traffic spikes for IoT data and AI recommendations
"""
import time
from collections import defaultdict
from typing import Dict, List
from threading import Lock

from fastapi import HTTPException, status


class RateLimiter:
    """
    In-memory rate limiter with sliding window algorithm.
    Thread-safe for concurrent requests.
    """
    
    def __init__(self, max_requests: int = 50, window_seconds: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()  # Thread-safe lock
    
    def check_rate_limit(self, key: str) -> tuple[bool, int]:
        """
        Check if request is still within rate limit
        
        Args:
            key: Unique key for rate limiting (can be user_id, IP, or endpoint)
        
        Returns:
            Tuple (is_allowed, retry_after_seconds)
            - is_allowed: True if request is allowed
            - retry_after_seconds: Seconds to wait before retry (0 if allowed)
        """
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Clean old requests outside the window
            if key in self._requests:
                self._requests[key] = [
                    req_time for req_time in self._requests[key]
                    if req_time > window_start
                ]
            
            # Check if limit is reached
            request_count = len(self._requests[key])
            
            if request_count >= self.max_requests:
                # Calculate retry after (time until oldest request expires)
                if self._requests[key]:
                    oldest_request = min(self._requests[key])
                    retry_after = int(self.window_seconds - (now - oldest_request)) + 1
                else:
                    retry_after = self.window_seconds
                
                return False, retry_after
            
            # Add current request
            self._requests[key].append(now)
            return True, 0
    
    def get_remaining_requests(self, key: str) -> int:
        """Get remaining requests for a specific key"""
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            if key in self._requests:
                self._requests[key] = [
                    req_time for req_time in self._requests[key]
                    if req_time > window_start
                ]
                return max(0, self.max_requests - len(self._requests[key]))
            return self.max_requests
    
    def reset(self, key: str = None):
        """Reset rate limit for a specific key or all keys"""
        with self._lock:
            if key:
                if key in self._requests:
                    del self._requests[key]
            else:
                self._requests.clear()


# Global rate limiter instances
# IoT Data Endpoints: 50 requests/minute
iot_data_limiter = RateLimiter(max_requests=50, window_seconds=60)

# AI Recommendation Endpoints: 30 requests/minute
ai_recommendation_limiter = RateLimiter(max_requests=30, window_seconds=60)


def get_rate_limit_exception(limiter: RateLimiter, retry_after: int) -> HTTPException:
    """Create HTTPException for rate limit exceeded"""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "Too many requests. Please wait.",
            "retry_after": retry_after,
            "limit": limiter.max_requests,
            "window_seconds": limiter.window_seconds
        },
        headers={"Retry-After": str(retry_after)}
    )






