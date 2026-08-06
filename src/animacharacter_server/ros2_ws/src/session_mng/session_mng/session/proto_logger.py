from typing import Protocol, Any

class LoggerLike(Protocol):
    def info(self, msg: str, /, **kwargs: Any) -> Any: ...
    def warning(self, msg: str, /, **kwargs: Any) -> Any: ...
    def error(self, msg: str, /, **kwargs: Any) -> Any: ...

class StupidLogger:
    def info(self, msg: str, **kwargs: object) -> Any:
        print(f"[INFO] {msg}", *kwargs)
    def warning(self, msg: str, **kwargs: object) -> Any:
        print(f"[WARNING] {msg}", *kwargs)
    def error(self, msg: str, **kwargs: object) -> Any:    
        print(f"[ERROR] {msg}", *kwargs)
