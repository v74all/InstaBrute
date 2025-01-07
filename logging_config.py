import logging
import os
from datetime import datetime

def setup_logging(name: str = None, log_file: str = None) -> logging.Logger:
    if log_file is None:
        os.makedirs('logs', exist_ok=True)
        log_file = f'logs/instabrute_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

    logger = logging.getLogger(name or __name__)
    
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        logger.setLevel(logging.INFO)
    
    return logger
