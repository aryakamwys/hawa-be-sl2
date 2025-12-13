"""
Shared service for Google Sheets caching
Reduces cache logic duplication in admin.py and weather.py
Improved with thread-safety, auto cleanup, and memory limit
"""
import time
import threading
from collections import OrderedDict
from typing import Dict, List, Any, Tuple

from app.services.weather.spreadsheet_service import SpreadsheetService


class SheetsCacheService:
    """
    Improved service to cache Google Sheets data with TTL.
    Features:
    - Thread-safe for concurrent requests
    - Auto cleanup expired entries (prevent memory leak)
    - Memory limit (prevent OOM)
    - Better error handling
    """
    
    def __init__(self, ttl_seconds: int = 30, max_size: int = 500):
        """
        Initialize cache service
        
        Args:
            ttl_seconds: Time to live in seconds
            max_size: Maximum entries in cache
        """
        self._cache: OrderedDict[str, Tuple[List[Dict[str, Any]], float]] = OrderedDict()
        self._lock = threading.RLock()  # Reentrant lock
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._service = SpreadsheetService()
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every 60 seconds
    
    def get_cached_data(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get Google Sheets data with caching to reduce API calls
        
        Args:
            spreadsheet_id: Google Sheets ID
            worksheet_name: Worksheet name
            force_refresh: Force refresh from Google Sheets (bypass cache)
        
        Returns:
            List of dictionaries with data from spreadsheet
        """
        cache_key = f"{spreadsheet_id}:{worksheet_name}"
        current_time = time.time()
        
        # Periodic cleanup
        self._periodic_cleanup()
        
        with self._lock:
            # Check cache if not force refresh
            if not force_refresh and cache_key in self._cache:
                cached_data, cache_timestamp = self._cache[cache_key]
                if current_time - cache_timestamp < self.ttl_seconds:
                    # Move to end (LRU)
                    self._cache.move_to_end(cache_key)
                    return cached_data
                else:
                    # Expired, remove from cache
                    del self._cache[cache_key]
        
        # Fetch fresh data
        try:
            raw_data = self._service.read_from_google_sheets(
                spreadsheet_id=spreadsheet_id,
                worksheet_name=worksheet_name
            )
            
            with self._lock:
                # Remove oldest if at max size
                if len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
                
                self._cache[cache_key] = (raw_data, current_time)
            
            return raw_data
        except Exception as e:
            # Fallback to cached data if rate limit or error
            with self._lock:
                if cache_key in self._cache:
                    error_msg = str(e)
                    if "429" in error_msg or "Quota exceeded" in error_msg or "rate limit" in error_msg.lower():
                        cached_data, _ = self._cache[cache_key]
                        return cached_data
            raise
    
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
    
    def clear_cache(self):
        """Clear all cached data"""
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


# Global instances for shared cache
# Standard cache (30 seconds for normal use)
_sheets_cache_service = SheetsCacheService(ttl_seconds=30, max_size=500)

# Realtime cache (1 second for realtime data)
_realtime_cache_service = SheetsCacheService(ttl_seconds=1, max_size=500)


def get_cached_sheets_data(
    spreadsheet_id: str,
    worksheet_name: str,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Convenience function to get cached sheets data
    Uses global cache service instance (standard cache)
    """
    return _sheets_cache_service.get_cached_data(
        spreadsheet_id=spreadsheet_id,
        worksheet_name=worksheet_name,
        force_refresh=force_refresh
    )


def get_realtime_sheets_data(
    spreadsheet_id: str,
    worksheet_name: str,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Get cached sheets data with 1 second TTL for realtime data
    Uses realtime cache service instance
    """
    return _realtime_cache_service.get_cached_data(
        spreadsheet_id=spreadsheet_id,
        worksheet_name=worksheet_name,
        force_refresh=force_refresh
    )


