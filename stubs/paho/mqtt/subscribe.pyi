from .. import mqtt as mqtt
from _typeshed import Incomplete

def callback(callback, topics, qos: int = ..., userdata: Incomplete | None = ..., hostname: str = ..., port: int = ..., client_id: str = ..., keepalive: int = ..., will: Incomplete | None = ..., auth: Incomplete | None = ..., tls: Incomplete | None = ..., protocol=..., transport: str = ..., clean_session: bool = ..., proxy_args: Incomplete | None = ...) -> None: ...
def simple(topics, qos: int = ..., msg_count: int = ..., retained: bool = ..., hostname: str = ..., port: int = ..., client_id: str = ..., keepalive: int = ..., will: Incomplete | None = ..., auth: Incomplete | None = ..., tls: Incomplete | None = ..., protocol=..., transport: str = ..., clean_session: bool = ..., proxy_args: Incomplete | None = ...): ...