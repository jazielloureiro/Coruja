from os import getenv

from psycopg import connect

from common import Singleton

class PostgresConnection(metaclass=Singleton):
    def __init__(self):
        self._connection = connect(f'postgresql://{getenv('POSTGRES_USER')}:{getenv('POSTGRES_PASSWORD')}@{getenv('POSTGRES_URL')}/{getenv('POSTGRES_DB')}')

    def __call__(self):
        return self._connection