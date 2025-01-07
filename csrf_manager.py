import requests
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional
import logging
import time
from logging_config import setup_logging

logger = setup_logging('CSRFManager')

class CSRFManager:
    def __init__(self, login_url="https://www.instagram.com/accounts/login/", timeout=10, cache_duration=15):
        self.login_url = login_url
        self.timeout = timeout
        self.cache_duration = timedelta(minutes=cache_duration)
        self.token_cache = {}
        self.last_request_time = None

    @lru_cache(maxsize=100)
    def get_csrf_token(self, use_proxy=False, proxy=None):
        cached_token = self.get_cached_token()
        if cached_token:
            logger.info("[INFO] Returning cached CSRF token.")
            return cached_token

        proxies = proxy if use_proxy else None
        try:
            logger.info("[INFO] Fetching CSRF token...")
            response = requests.get(self.login_url, proxies=proxies, timeout=self.timeout)
            if response.status_code == 200:
                csrf_token = response.cookies.get('csrftoken')
                if csrf_token:
                    logger.info("[INFO] CSRF token successfully fetched.")
                    self.cache_token(csrf_token)
                    return csrf_token
                else:
                    logger.error("[ERROR] Failed to extract CSRF token from cookies.")
            else:
                logger.error(f"[ERROR] Failed to fetch CSRF token. HTTP Status Code: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"[ERROR] Exception occurred while fetching CSRF token: {e}")
        return None

    def cache_token(self, token: str):
        self.token_cache = {
            'token': token,
            'timestamp': datetime.now()
        }
        logger.info("[INFO] CSRF token cached.")

    def get_cached_token(self) -> Optional[str]:
        if not self.token_cache:
            return None
            
        if datetime.now() - self.token_cache['timestamp'] < self.cache_duration:
            return self.token_cache['token']
        else:
            logger.info("[INFO] Cached CSRF token expired.")
        return None

    def refresh_csrf_token(self, use_proxy=False, proxy=None):
        logger.info("[INFO] Refreshing CSRF token...")
        return self.get_csrf_token(use_proxy, proxy)

    def validate_csrf_token(self, csrf_token, use_proxy=False, proxy=None):
        headers = {'X-CSRFToken': csrf_token}
        proxies = proxy if use_proxy else None
        try:
            response = requests.get(self.login_url, headers=headers, proxies=proxies, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("[INFO] CSRF token is valid.")
                return True
            else:
                logger.error(f"[ERROR] CSRF token validation failed. HTTP Status Code: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"[ERROR] Exception occurred while validating CSRF token: {e}")
        return False

    def retry_request(self, func, retries=3, delay=2, *args, **kwargs):
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except requests.RequestException as e:
                logger.warning(f"[WARNING] Request failed: {e}. Retrying {attempt + 1}/{retries}...")
                time.sleep(delay)
        logger.error("[ERROR] All retries failed.")
        return None

def get_csrf_token(use_proxy=False, proxy=None):
    csrf_manager = CSRFManager()
    return csrf_manager.get_csrf_token(use_proxy, proxy)

if __name__ == "__main__":
    csrf_manager = CSRFManager()
    csrf_token = csrf_manager.get_csrf_token()
    if csrf_token:
        logger.info(f"Fetched CSRF Token: {csrf_token}")
        if csrf_manager.validate_csrf_token(csrf_token):
            refreshed_token = csrf_manager.refresh_csrf_token()
            logger.info(f"Refreshed CSRF Token: {refreshed_token}")
        else:
            logger.error("Invalid CSRF token.")
    else:
        logger.error("Failed to fetch CSRF token.")
