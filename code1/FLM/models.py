"""Data models used in the FLM scraper."""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SubjectInfo:
    """Represents basic information about a subject."""
    name: str
    data: List[str]
    link: Optional[str] = None
    parent: str = ""
    combo: str = ""

@dataclass
class ParsedBlock:
    """Represents a parsed text block with subject code and key-value pairs."""
    subject_code: str
    content: dict 