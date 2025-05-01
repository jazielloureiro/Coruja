from entities import Chatbot

from .connection import PostgresConnection

class PostgresChatbotRepository():
    def __init__(self):
        self._connection = PostgresConnection()
    
    def find_all(self) -> list[Chatbot]:
        chatbots = []

        with self._connection().cursor() as cursor:
            cursor.execute('SELECT id, token, name, username FROM chatbot ORDER BY name')

            for data in cursor:
                chatbots.append(Chatbot(*data))

        return chatbots
    
    def save(self, chatbot: Chatbot) -> None:
        with self._connection().cursor() as cursor:
            cursor.execute('INSERT INTO chatbot (token, name, username) VALUES (%s, %s, %s)', (chatbot.token, chatbot.name, chatbot.username))