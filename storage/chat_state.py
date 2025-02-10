import pickle

from entities.chat_state import ChatState

from .connection import ValkeyConnection

class ChatStateStorage:
    def __init__(self):
        self._connection = ValkeyConnection()
    
    def find(self, bot_username, chat_id) -> ChatState | None:
        chat_state = self._connection().get(f'chat_state_{bot_username}_{chat_id}')

        if chat_state:
            chat_state = pickle.loads(chat_state)
        
        return chat_state
    
    def save(self, chat_state: ChatState) -> None:
        self._connection().set(f'chat_state_{chat_state.bot_username}_{chat_state.chat_id}', pickle.dumps(chat_state))
