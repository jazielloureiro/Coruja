from entities import Resource

from .connection import PostgresConnection

class PostgresResourceRepository:
    def __init__(self):
        self._connection = PostgresConnection()
    
    def find(self, chatbot_id: int) -> list[Resource]:
        resources = []

        with self._connection().cursor() as cursor:
            cursor.execute('SELECT id, name FROM resource WHERE chatbot_id = %s ORDER BY name', (chatbot_id,))

            for id, name in cursor:
                resources.append(Resource(id, chatbot_id, name))
        
        return resources
    
    def save(self, resource: Resource) -> int:
        with self._connection().cursor() as cursor:
            cursor.execute('INSERT INTO resource (chatbot_id, name) VALUES (%s, %s) RETURNING id', (resource.chatbot_id, resource.name))
            
            return cursor.fetchone()[0]