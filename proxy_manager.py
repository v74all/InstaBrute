import random
import requests
from dataclasses import dataclass
from typing import List, Dict, Optional
import aiohttp
import asyncio
import time
import threading
from queue import Queue
from request_manager import RequestManager
from logging_config import setup_logging

@dataclass
class ProxyStats:
    success: int = 0
    failure: int = 0
    last_used: float = 0
    response_time: float = 0

class ProxyManager:
    def __init__(self, proxy_file=None, api_url=None, test_url="https://www.google.com", timeout=5, min_proxy_rotation_interval=30, max_concurrent_validations=10):
        self.logger = setup_logging('ProxyManager')
        self.proxies = []
        self.api_url = api_url
        self.proxy_file = proxy_file
        self.test_url = test_url
        self.timeout = timeout
        self.proxy_stats: Dict[str, ProxyStats] = {}
        self.min_proxy_rotation_interval = min_proxy_rotation_interval
        self.request_manager = RequestManager()
        self.proxy_pool = Queue()
        self.lock = threading.Lock()
        self.max_concurrent_validations = max_concurrent_validations
        self.semaphore = asyncio.Semaphore(self.max_concurrent_validations)

    def fetch_proxies_from_api(self):
        if not self.api_url:
            print("[WARNING] No API URL provided for fetching proxies.")
            return

        try:
            print(f"[INFO] Fetching proxies from API: {self.api_url}")
            response = requests.get(self.api_url, timeout=self.timeout)
            if response.status_code == 200:
                self.proxies = [proxy.strip() for proxy in response.text.splitlines() if proxy.strip()]
                print(f"[INFO] {len(self.proxies)} proxies fetched from API.")
            else:
                print(f"[ERROR] Failed to fetch proxies from API. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"[ERROR] Error fetching proxies from API: {e}")

    def fetch_proxies_from_new_api(self, new_api_url):
        try:
            print(f"[INFO] Fetching proxies from new API: {new_api_url}")
            response = requests.get(new_api_url, timeout=self.timeout)
            if response.status_code == 200:
                self.proxies = [proxy.strip() for proxy in response.text.splitlines() if proxy.strip()]
                print(f"[INFO] {len(self.proxies)} proxies fetched from new API.")
            else:
                print(f"[ERROR] Failed to fetch proxies from new API. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"[ERROR] Error fetching proxies from new API: {e}")

    def reformat_proxy(self, proxy):
        if not proxy.startswith("http://") and not proxy.startswith("https://"):
            return f"http://{proxy}"
        return proxy

    def load_proxies_from_file(self):
        if not self.proxy_file:
            print("[WARNING] No proxy file provided.")
            return

        try:
            with open(self.proxy_file, 'r') as file:
                self.proxies = [self.reformat_proxy(line.strip()) for line in file.readlines() if line.strip()]
            print(f"[INFO] Loaded {len(self.proxies)} proxies from {self.proxy_file}.")
        except FileNotFoundError:
            print(f"[ERROR] Proxy file not found: {self.proxy_file}")

    def get_random_proxy(self):
        if not self.proxies:
            print("[WARNING] No proxies available.")
            return None
        proxy = random.choice(self.proxies)
        return {'http': proxy, 'https': proxy}

    def get_next_proxy(self):
        with self.lock:
            if self.proxy_pool.empty():
                return None

            proxy = self.proxy_pool.get()
            time_since_last_used = time.time() - self.proxy_stats[proxy].last_used

            if time_since_last_used < self.min_proxy_rotation_interval:
                self.proxy_pool.put(proxy)
                return self.get_next_proxy()

            return proxy

    def update_proxy_stats(self, proxy: str, success: bool, response_time: float = 0):
        if proxy not in self.proxy_stats:
            self.proxy_stats[proxy] = ProxyStats()

        stats = self.proxy_stats[proxy]
        if success:
            stats.success += 1
            stats.response_time = response_time
        else:
            stats.failure += 1
        stats.last_used = time.time()

    def initialize_proxies(self):
        if self.api_url:
            self.fetch_proxies_from_api()

        if not self.proxies and self.proxy_file:
            print("[INFO] Falling back to local proxy file.")
            self.load_proxies_from_file()

        if not self.proxies:
            print("[ERROR] No proxies available from API or file.")
            return

        for proxy in self.proxies:
            self.proxy_pool.put(proxy)

    def save_valid_proxies(self, file_path):
        try:
            with open(file_path, 'w') as file:
                for proxy in self.proxies:
                    file.write(f"{proxy}\n")
            print(f"[INFO] Valid proxies saved to {file_path}.")
        except IOError:
            print(f"[ERROR] Failed to save proxies to {file_path}.")

    async def _check_proxy_health(self, proxy: str) -> bool:
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    start_time = time.time()
                    async with session.get(self.test_url, proxy=proxy, timeout=self.timeout) as response:
                        response_time = time.time() - start_time
                        self.update_proxy_stats(proxy, True, response_time)
                        return response.status == 200
                except Exception as e:
                    print(f"[ERROR] Error validating proxy {proxy}: {e}")
                    self.update_proxy_stats(proxy, False)
                    return False

    async def validate_all_proxies(self):
        print("[INFO] Validating proxies...")
        valid_proxies = []
        tasks = [self._check_proxy_health(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks)

        for proxy, is_valid in zip(self.proxies, results):
            if is_valid:
                valid_proxies.append(proxy)
                print(f"[INFO] Proxy valid: {proxy}")
            else:
                print(f"[WARNING] Proxy invalid: {proxy}")

        self.proxies = valid_proxies
        print(f"[INFO] {len(valid_proxies)} valid proxies found.")

    def get_best_proxy(self) -> Optional[str]:
        valid_proxies = [p for p in self.proxies if self.is_proxy_valid(p)]
        if not valid_proxies:
            return None

        best_proxy = min(
            valid_proxies,
            key=lambda p: (
                self.proxy_stats[p].failure / max(1, self.proxy_stats[p].success),
                self.proxy_stats[p].response_time
            )
        )

        return best_proxy

    def validate_proxy(self, proxy: str, timeout: int = 5) -> bool:
        try:
            proxies = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            response = requests.get(
                'https://www.google.com',
                proxies=proxies,
                timeout=timeout
            )
            return response.status_code == 200
        except:
            return False


if __name__ == "__main__":
    api_url = "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc"
    proxy_file = "proxies.txt"
    valid_proxy_file = "valid_proxies.txt"

    proxy_manager = ProxyManager(proxy_file=proxy_file, api_url=api_url)
    proxy_manager.initialize_proxies()

    asyncio.run(proxy_manager.validate_all_proxies())

    proxy_manager.save_valid_proxies(valid_proxy_file)

    new_api_url = "https://newproxyapi.com/api/proxy-list"
    proxy_manager.fetch_proxies_from_new_api(new_api_url)
