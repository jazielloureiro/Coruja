from dataclasses import dataclass

@dataclass()
class Resource:
    id: int
    chatbot_id: int
    name: str