from dataclasses import dataclass

@dataclass()
class Chatbot:
    id: int = 0
    token: str = ''
    name: str = ''
    username: str = ''