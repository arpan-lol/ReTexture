import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    max_requests: int
    window_minutes: int
    
    def __str__(self):
        return f"{self.max_requests} requests per {self.window_minutes} minutes"


class RateLimiter:

    def __init__(self, max_requests: int = 10, window_minutes: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            window_minutes: Time window in minutes
        """
        self.config = RateLimitConfig(max_requests, window_minutes)
        self._requests: Dict[str, List[datetime]] = {}
        self._lock = Lock()
        
        logger.info(f"Rate limiter initialized: {self.config}")
    
    def check_limit(self, key: str) -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            key: Identifier for rate limiting (user_id, design_id, IP, etc.)
            
        Returns:
            True if request is allowed, False if limit exceeded
        """
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=self.config.window_minutes)
            
            # Initialize or clean old entries
            if key not in self._requests:
                self._requests[key] = []
            else:
                # Remove requests outside the window
                self._requests[key] = [
                    ts for ts in self._requests[key] 
                    if ts > cutoff
                ]
            
            # Check limit
            current_count = len(self._requests[key])
            
            if current_count >= self.config.max_requests:
                logger.warning(
                    f"Rate limit exceeded for key={key}: "
                    f"{current_count}/{self.config.max_requests} in window"
                )
                return False
            
            # Record this request
            self._requests[key].append(now)
            
            logger.debug(
                f"Rate limit check passed for key={key}: "
                f"{current_count + 1}/{self.config.max_requests}"
            )
            
            return True
    
    def get_limit_info(self, key: str) -> Dict[str, any]:
        """
        Get current rate limit status for a key.
        
        Args:
            key: Identifier to check
            
        Returns:
            Dictionary with limit information
        """
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=self.config.window_minutes)
            
            if key not in self._requests:
                current_count = 0
                oldest_request = None
            else:
                # Clean old entries
                self._requests[key] = [
                    ts for ts in self._requests[key] 
                    if ts > cutoff
                ]
                current_count = len(self._requests[key])
                oldest_request = min(self._requests[key]) if self._requests[key] else None
            
            remaining = max(0, self.config.max_requests - current_count)
            
            # Calculate when limit resets (when oldest request expires)
            if oldest_request:
                reset_time = oldest_request + timedelta(minutes=self.config.window_minutes)
                seconds_until_reset = (reset_time - now).total_seconds()
            else:
                seconds_until_reset = 0
            
            return {
                "limit": self.config.max_requests,
                "remaining": remaining,
                "used": current_count,
                "window_minutes": self.config.window_minutes,
                "reset_in_seconds": max(0, int(seconds_until_reset))
            }
    
    def reset_key(self, key: str):
        """
        Reset rate limit for a specific key (admin/testing use).
        
        Args:
            key: Identifier to reset
        """
        with self._lock:
            if key in self._requests:
                del self._requests[key]
                logger.info(f"Rate limit reset for key={key}")
    
    def cleanup_old_entries(self, max_age_hours: int = 24):
        """
        Clean up very old entries to prevent memory leaks.
        
        Call this periodically (e.g., daily) to remove stale data.
        
        Args:
            max_age_hours: Remove entries older than this
        """
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(hours=max_age_hours)
            
            keys_to_remove = []
            
            for key, timestamps in self._requests.items():
                # Remove old timestamps
                self._requests[key] = [ts for ts in timestamps if ts > cutoff]
                
                # If no recent activity, remove key entirely
                if not self._requests[key]:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._requests[key]
            
            if keys_to_remove:
                logger.info(f"Cleaned up {len(keys_to_remove)} inactive rate limit keys")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about rate limiter.
        
        Returns:
            Dictionary with stats
        """
        with self._lock:
            return {
                "total_keys": len(self._requests),
                "config": {
                    "max_requests": self.config.max_requests,
                    "window_minutes": self.config.window_minutes
                }
            }


# Global rate limiters for different features
_headline_limiter: Optional[RateLimiter] = None
_generation_limiter: Optional[RateLimiter] = None


def get_headline_rate_limiter() -> RateLimiter:
    """Get or create rate limiter for headline generation"""
    global _headline_limiter
    if _headline_limiter is None:
        _headline_limiter = RateLimiter(max_requests=10, window_minutes=60)
    return _headline_limiter


def get_generation_rate_limiter() -> RateLimiter:
    """Get or create rate limiter for image generation"""
    global _generation_limiter
    if _generation_limiter is None:
        # More restrictive for expensive operations
        _generation_limiter = RateLimiter(max_requests=20, window_minutes=60)
    return _generation_limiter
