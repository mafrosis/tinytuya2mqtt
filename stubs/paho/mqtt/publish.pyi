from .. import mqtt as mqtt
from _typeshed import Incomplete

def multiple(msgs, hostname: str = ..., port: int = ..., client_id: str = ..., keepalive: int = ..., will: Incomplete | None = ..., auth: Incomplete | None = ..., tls: Incomplete | None = ..., protocol=..., transport: str = ..., proxy_args: Incomplete | None = ...) -> None: ...
def single(topic, payload: Incomplete | None = ..., qos: int = ..., retain: bool = ..., hostname: str = ..., port: int = ..., client_id: str = ..., keepalive: int = ..., will: Incomplete | None = ..., auth: Incomplete | None = ..., tls: Incomplete | None = ..., protocol=..., transport: str = ..., proxy_args: Incomplete | None = ...) -> None: ...