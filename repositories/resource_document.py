from entities import ResourceDocument

from .connection import PostgresConnection

class PostgresResourceDocumentRepository:
    def __init__(self):
        self._connection = PostgresConnection()
    
    def save_many(self, resource_documents: list[ResourceDocument]) -> None:
        with self._connection().cursor() as cursor:
            cursor.executemany('INSERT INTO resource_document (resource_id, document_id) VALUES (%s, %s)', [(i.resource_id, i.document_id) for i in resource_documents])