from typing import Dict

import json
with open('pass_cloud.json') as f:
    password = json.load(f)

timeout = 10
# Thông tin kết nối database
DB_CONFIG: Dict = {
    "host": "mysql-1351591c-fap-chat.l.aivencloud.com",
    "user": "avnadmin",
    "password": password['pass_cloud'],
    "db": "FAP_chat",
    "port": 19116,
    "charset": "utf8mb4",
    "connect_timeout": timeout,
    "read_timeout": timeout,
    "write_timeout": timeout,
    "cursorclass": "DictCursor"
} 