"""
AI Recommendation Cache Service
Cache for AI-generated recommendations with 1 second TTL
Thread-safe with auto cleanup to prevent memory leaks
"""
import json
import hashlib
import threading
import time
from collections import OrderedDict
from typing import Dict, Any, Optional, Tuple


class AICacheService:
    """
    Improved in-memory cache for AI recommendations.
    Features:
    - Thread-safe for concurrent requests
    - Auto cleanup expired entries (prevent memory leak)
    - Memory limit (prevent OOM)
    - TTL-based expiration
    """
    
    def __init__(self, ttl_seconds: int = 1, max_size: int = 1000):
        """
        Initialize AI cache service
        
        Args:
            ttl_seconds: Time to live in seconds (default: 1 second for realtime)
            max_size: Maximum entries in cache (prevent memory overflow)
        """
        self._cache: OrderedDict[str, Tuple[Dict[str, Any], float]] = OrderedDict()
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every 60 seconds
    
    def get_cached_recommendation(
        self,
        cache_key: str,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached recommendation if still valid
        
        Args:
            cache_key: Cache key for recommendation
            force_refresh: Force refresh (bypass cache)
        
        Returns:
            Cached recommendation or None if cache miss/expired
        """
        if force_refresh:
            return None
        
        with self._lock:
            # Periodic cleanup
            self._periodic_cleanup()
            
            if cache_key not in self._cache:
                return None
            
            value, timestamp = self._cache[cache_key]
            current_time = time.time()
            
            # Check if expired
            if current_time - timestamp >= self.ttl_seconds:
                del self._cache[cache_key]
                return None
            
            # Move to end (LRU - Least Recently Used)
            self._cache.move_to_end(cache_key)
            return value
    
    def set_cached_recommendation(
        self,
        cache_key: str,
        recommendation: Dict[str, Any]
    ):
        """
        Set cached recommendation
        
        Args:
            cache_key: Cache key for recommendation
            recommendation: Recommendation data to cache
        """
        with self._lock:
            # Remove oldest if at max size
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Remove oldest (FIFO)
            
            self._cache[cache_key] = (recommendation, time.time())
    
    def _periodic_cleanup(self):
        """Periodic cleanup expired entries"""
        current_time = time.time()
        
        # Only cleanup at certain intervals for performance
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = current_time
        self.cleanup_expired()
    
    def cleanup_expired(self):
        """Remove expired entries"""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp >= self.ttl_seconds
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def clear(self):
        """Clear all cache"""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            current_time = time.time()
            total_entries = len(self._cache)
            expired_count = sum(
                1 for _, (_, timestamp) in self._cache.items()
                if current_time - timestamp >= self.ttl_seconds
            )
            
            return {
                "total_entries": total_entries,
                "valid_entries": total_entries - expired_count,
                "expired_entries": expired_count,
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds
            }


def generate_cache_key(user_id: int, weather_data: Dict[str, Any]) -> str:
    """
    Generate cache key untuk AI recommendation
    
    Args:
        user_id: User ID
        weather_data: Weather data dictionary
    
    Returns:
        Cache key string
    """
    # Create hash from weather data for unique key
    data_str = json.dumps(weather_data, sort_keys=True, default=str)
    data_hash = hashlib.md5(data_str.encode()).hexdigest()[:8]
    return f"ai_rec_{user_id}_{data_hash}"


# Global instance for shared cache
_ai_cache_service = AICacheService(ttl_seconds=1, max_size=1000)


def get_ai_cache_service() -> AICacheService:
    """Get global AI cache service instance"""
    return _ai_cache_service






