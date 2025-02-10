from dataclasses import dataclass

@dataclass()
class Chatbot:
    id: int
    token: str
    name: str
    username: str