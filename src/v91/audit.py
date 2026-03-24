import hashlib
import json
import os
from datetime import datetime

class AuditLogger:
    def __init__(self, log_file):
        self.log_file = log_file
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                f.write('[]')  # Initialize with an empty JSON array

    def log(self, action, user, additional_info=None):
        timestamp = datetime.utcnow().isoformat()
        entry = {
            'timestamp': timestamp,
            'action': action,
            'user': user,
            'additional_info': additional_info
        }
        entry_hash = self.calculate_hash(entry)
        log_entry = {**entry, 'hash': entry_hash}
        
        self.append_log(log_entry)

    def calculate_hash(self, entry):
        entry_json = json.dumps(entry, sort_keys=True)
        return hashlib.sha256(entry_json.encode('utf-8')).hexdigest()

    def append_log(self, log_entry):
        with open(self.log_file, 'r+') as f:
            logs = json.load(f)
            logs.append(log_entry)
            f.seek(0)
            json.dump(logs, f, indent=4)
            f.truncate()

# Usage example
# logger = AuditLogger('audit_log.json')
# logger.log('UserLogin', 'guenny9000', 'Logged in successfully')
