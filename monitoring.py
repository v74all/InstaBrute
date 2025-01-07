import time
import logging
import psutil
import threading
import asyncio
from datetime import datetime
from logging_config import setup_logging
from typing import Dict, Any

class OperationMonitor:
    def __init__(self):
        self.logger = setup_logging('OperationMonitor')
        self.active = False
        self._lock = threading.Lock()
        self._task = None
        self.stats = {
            'requests_sent': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'last_request_time': None,
            'start_time': None,
            'cpu_usage': [],
            'memory_usage': [],
            'active_threads': 0
        }

    def start_monitoring(self):
        self.active = True
        self.stats['start_time'] = datetime.now()
        self.logger.info("Monitoring started")
        
        if asyncio.get_event_loop().is_running():
            self._task = asyncio.create_task(self._monitor_resources_async())
        else:
            threading.Thread(target=self._monitor_resources, daemon=True).start()

    def stop_monitoring(self):
        self.active = False
        self._generate_report()

    async def _monitor_resources_async(self):
        while self.active:
            with self._lock:
                self.stats['cpu_usage'].append(psutil.cpu_percent())
                self.stats['memory_usage'].append(psutil.Process().memory_percent())
                self.stats['active_threads'] = threading.active_count()
            await asyncio.sleep(1)

    def _monitor_resources(self):
        while self.active:
            self.stats['cpu_usage'].append(psutil.cpu_percent())
            self.stats['memory_usage'].append(psutil.Process().memory_percent())
            self.stats['active_threads'] = threading.active_count()
            time.sleep(1)

    def log_request(self, success: bool):
        self.stats['requests_sent'] += 1
        self.stats['last_request_time'] = datetime.now()
        if success:
            self.stats['successful_requests'] += 1
        else:
            self.stats['failed_requests'] += 1

    def get_current_status(self) -> dict:
        if not self.stats['start_time']:
            return {"status": "Not started"}

        elapsed_time = (datetime.now() - self.stats['start_time']).seconds
        return {
            "running_time": elapsed_time,
            "requests_sent": self.stats['requests_sent'],
            "success_rate": (self.stats['successful_requests'] / max(1, self.stats['requests_sent'])) * 100,
            "active_threads": self.stats['active_threads'],
            "avg_cpu_usage": sum(self.stats['cpu_usage'][-10:]) / min(10, len(self.stats['cpu_usage'])),
            "avg_memory_usage": sum(self.stats['memory_usage'][-10:]) / min(10, len(self.stats['memory_usage']))
        }

    def verify_operation(self) -> bool:
        current_status = self.get_current_status()
        
        if current_status.get("running_time", 0) > 0:
            if current_status["requests_sent"] == 0:
                self.logger.error("No requests sent!")
                return False
                
            if current_status["active_threads"] < 1:
                self.logger.error("No active threads!")
                return False

            if current_status["success_rate"] < 1:
                self.logger.warning("Very low success rate!")
                
        return True

    def log_error(self, error_type: str, details: str):
        if 'errors' not in self.stats:
            self.stats['errors'] = {}
            
        if error_type not in self.stats['errors']:
            self.stats['errors'][error_type] = []
            
        self.stats['errors'][error_type].append({
            'time': datetime.now(),
            'details': details
        })
        self.logger.error(f"{error_type}: {details}")

    def _generate_report(self):
        final_stats = self.get_current_status()
        report = ["Operation Report", "---------------"]
        
        report.extend([
            f"Duration: {final_stats['running_time']} seconds",
            f"Total Requests: {self.stats['requests_sent']}",
            f"Successful Requests: {self.stats['successful_requests']}",
            f"Failed Requests: {self.stats['failed_requests']}",
            f"Success Rate: {final_stats['success_rate']:.2f}%",
            f"Average CPU Usage: {final_stats['avg_cpu_usage']:.2f}%",
            f"Average Memory Usage: {final_stats['avg_memory_usage']:.2f}%",
            f"Active Threads: {final_stats['active_threads']}"
        ])
        
        if 'errors' in self.stats and self.stats['errors']:
            report.extend(["", "Error Summary:", "-------------"])
            for error_type, errors in self.stats['errors'].items():
                report.append(f"{error_type}: {len(errors)} occurrences")
        
        report_text = "\n".join(report)
        self.logger.info(report_text)
        with open('operation_report.txt', 'w') as f:
            f.write(report_text)
