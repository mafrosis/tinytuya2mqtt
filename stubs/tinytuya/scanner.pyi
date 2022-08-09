from _typeshed import Incomplete
from audioop import add as add
from hashlib import md5 as md5

SCANLIBS: bool
input = raw_input
DEVICEFILE: Incomplete
SNAPSHOTFILE: Incomplete
DEFAULT_NETWORK: Incomplete
TCPTIMEOUT: Incomplete
TCPPORT: Incomplete
MAXCOUNT: Incomplete
UDPPORT: Incomplete
UDPPORTS: Incomplete
TIMEOUT: Incomplete
log: Incomplete

def getmyIP(): ...
def scan(maxretry: Incomplete | None = ..., color: bool = ..., forcescan: bool = ...) -> None: ...
def devices(verbose: bool = ..., maxretry: Incomplete | None = ..., color: bool = ..., poll: bool = ..., forcescan: bool = ..., byID: bool = ...): ...
def snapshot(color: bool = ...): ...
def alldevices(color: bool = ..., retries: Incomplete | None = ...): ...
def snapshotjson(): ...
