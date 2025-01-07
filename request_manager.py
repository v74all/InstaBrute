import time
import random
import logging
from contextlib import contextmanager
from typing import Optional, Dict
import aiohttp
import asyncio
from ratelimit import limits, sleep_and_retry
from logging_config import setup_logging

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []

    def allow_request(self) -> bool:
        current_time = time.time()
        self.requests = [req for req in self.requests if req > current_time - self.time_window]
        if len(self.requests) < self.max_requests:
            self.requests.append(current_time)
            return True
        return False

    def get_delay(self) -> float:
        if not self.requests:
            return 0
        return self.time_window - (time.time() - self.requests[0])

class RequestManager:
    def __init__(self, min_delay: float = 1.0, max_delay: float = 3.0):
        self.logger = setup_logging('RequestManager')
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0
        self.proxy_manager = None
        self.session = aiohttp.ClientSession()
        self.rate_limiter = RateLimiter(max_requests=30, time_window=60)

    def set_proxy_manager(self, proxy_manager):
        self.proxy_manager = proxy_manager

    @contextmanager
    def request_context(self, use_proxy: bool = False):
        proxy = self.get_proxy() if use_proxy else None
        try:
            if proxy:
                self.session.proxy = proxy
            yield self.session
        finally:
            if proxy:
                self.session.proxy = None
                self.rotate_proxy()

    async def handle_rate_limit(self, response):
        if response.status == 429:
            retry_after = int(response.headers.get('Retry-After', 30))
            self.logger.warning(f"Rate limit hit. Waiting {retry_after} seconds...")
            await asyncio.sleep(retry_after)
            return True
        return False

    async def send_request(self, url: str, headers: Dict, data: Dict, use_proxy: bool = False) -> Optional[aiohttp.ClientResponse]:
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            if not self.rate_limiter.allow_request():
                delay = self.rate_limiter.get_delay()
                self.logger.debug(f"Rate limit reached, waiting {delay:.2f}s")
                await asyncio.sleep(delay)
            
            try:
                async with self.request_context(use_proxy) as session:
                    self.enforce_delay()
                    async with session.post(url, headers=headers, data=data, timeout=10) as response:
                        if await self.handle_rate_limit(response):
                            retry_count += 1
                            continue
                        
                        self.last_request_time = time.time()
                        return response
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"Request failed: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(2 ** retry_count)
                    
        return None

    def enforce_delay(self):
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
        time.sleep(random.uniform(0, self.max_delay - self.min_delay))

    def get_proxy(self):
        return None

    def rotate_proxy(self):
        pass

async def main():
    request_manager = RequestManager(min_delay=1.0, max_delay=2.0)
    
    url = "https://httpbin.org/post"
    headers = {"User-Agent": "TestAgent"}
    data = {"key": "value"}
    
    response = await request_manager.send_request(url, headers, data)
    
    if response:
        print(await response.text())

if __name__ == "__main__":
    asyncio.run(main())
