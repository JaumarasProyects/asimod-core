from dataclasses import dataclass
from datetime import datetime

@dataclass
class ChatMessage:
    """Estructura de datos pura del core."""
    sender: str
    content: str
    timestamp: datetime = datetime.now()
