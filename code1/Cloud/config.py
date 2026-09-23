from typing import Dict
import os

from dotenv import load_dotenv

load_dotenv()

timeout = 10
# Thông tin kết nối database
DB_CONFIG: Dict = {
    "host": os.environ.get("MYSQL_HOST"),
    "user": os.environ.get("MYSQL_USER"),
    "password": os.environ.get("MYSQL_PASSWORD"),
    "db": os.environ.get("MYSQL_DB"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "charset": "utf8mb4",
    "connect_timeout": timeout,
    "read_timeout": timeout,
    "write_timeout": timeout,
    "cursorclass": "DictCursor"
}
