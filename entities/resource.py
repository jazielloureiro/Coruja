from dataclasses import dataclass

@dataclass()
class Resource:
    id: int = 0
    chatbot_id: int = 0
    name: str = ''