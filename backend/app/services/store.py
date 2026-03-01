import threading
from typing import Dict

from app.models.schemas import RunRecord


class InMemoryStore:
    def __init__(self) -> None:
        self.users: Dict[str, str] = {}
        self.tokens: Dict[str, str] = {}
        self.runs: Dict[str, RunRecord] = {}
        self.lock = threading.RLock()


store = InMemoryStore()
