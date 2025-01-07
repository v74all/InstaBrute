import subprocess
import time
import logging
import stem
from stem.control import Controller
from logging_config import setup_logging

logger = setup_logging('TorManager')

class TorManager:
    def __init__(self):
        self.logger = setup_logging('TorManager')
        self.last_identity_change = time.time()
        self.min_identity_change_interval = 30

    def _run_command(self, command: str) -> bool:
        try:
            result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            return False

    def change_identity(self):
        current_time = time.time()
        if current_time - self.last_identity_change < self.min_identity_change_interval:
            return False

        if self._run_command("killall -HUP tor"):
            time.sleep(3)
            self.last_identity_change = current_time
            return True
        return False

    def change_identity_via_control_port(self, password: str):
        current_time = time.time()
        if current_time - self.last_identity_change < self.min_identity_change_interval:
            return False

        try:
            with Controller.from_port(port=9051) as controller:
                controller.authenticate(password=password)
                controller.signal(stem.Signal.NEWNYM)
                self.last_identity_change = current_time
                return True
        except Exception as e:
            return False

    def ensure_tor_running(self):
        if not self._run_command("pgrep tor"):
            self.start_tor()
            time.sleep(5)
        
        if not self.check_tor_status():
            self.restart_tor()
            time.sleep(5)
        return self.check_tor_status()

    def check_tor_status(self):
        command = "curl --socks5-hostname localhost:9050 https://check.torproject.org/"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return True
        else:
            return False

    def stop_tor(self):
        if self._run_command("sudo systemctl stop tor"):
            pass
        else:
            pass

    def start_tor(self):
        if self._run_command("sudo systemctl start tor"):
            pass
        else:
            pass

    def restart_tor(self):
        if self._run_command("sudo systemctl restart tor"):
            pass
        else:
            pass

    def configure_tor(self):
        password = input("Enter control password for Tor: ")
        hashed_password_command = f"sudo tor --hash-password '{password}' > hashed_password.txt"
        append_password_command = f"sudo echo 'HashedControlPassword '$(cat hashed_password.txt) >> /etc/tor/torrc"
        control_port_command = "sudo echo 'ControlPort 9051' >> /etc/tor/torrc"
        
        if self._run_command(hashed_password_command) and \
           self._run_command(append_password_command) and \
           self._run_command(control_port_command):
            pass
        else:
            pass

    def restart_tor_if_needed(self):
        if not self.check_tor_status():
            self.restart_tor()
        else:
            pass


if __name__ == "__main__":
    tor_manager = TorManager()
    
    tor_manager.stop_tor()
    tor_manager.configure_tor()
    tor_manager.start_tor()
    tor_manager.change_identity()
    tor_manager.check_tor_status()
    tor_manager.restart_tor_if_needed()
