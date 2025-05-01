from entities import Chatbot
from repositories import ChatbotRepositoryABC

class ChatbotService:
    def __init__(self, chatbot_repository: ChatbotRepositoryABC):
        self._chatbot_repository = chatbot_repository

    def list_chatbots(self) -> list[Chatbot]:
        return self._chatbot_repository.find_all()