from threading import Lock

class Singleton(type):
    _instances = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):
        if not cls in cls._instances:
            cls._lock.acquire()

            if not cls in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        
        return cls._instances[cls]
