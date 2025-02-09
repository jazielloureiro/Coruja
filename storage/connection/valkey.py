from os import getenv

from valkey import Valkey

from common.singleton import Singleton

class ValkeyConnection(metaclass=Singleton):
    def __init__(self):
        self._connection = Valkey(host=getenv('VALKEY_HOST'), port=getenv('VALKEY_PORT'), db=getenv('VALKEY_DB'))

    def __call__(self):
        return self._connection