from dataclasses import dataclass

@dataclass()
class ChatState:
    bot_username: str
    chat_id: int
    child_bot_id: int = None
    child_bot_username: str = None