from datetime import datetime
from typing import Any, Dict, Optional

class FlightDetectorContext:
    def __init__(self) -> None:
        # Un diccionario flexible para guardar estado entre fases
        self.state: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.state.get(key, default)

    def has(self, key: str) -> bool:
        return key in self.state

    def clear(self) -> None:
        self.state.clear()