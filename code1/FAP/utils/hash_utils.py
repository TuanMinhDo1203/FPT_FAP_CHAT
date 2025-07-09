import hashlib
from typing import List

def content_hash(content: str) -> str:
    """
    Sinh mã hash SHA256 cho nội dung string.
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def is_duplicate_hash(content: str, existing_hashes: List[str]) -> bool:
    """
    Kiểm tra nội dung đã tồn tại trong danh sách hash chưa.
    """
    h = content_hash(content)
    return h in existing_hashes 