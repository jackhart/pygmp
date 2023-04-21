from dataclasses import dataclass

unicast_interfaces = None
multicast_interfaces = None



@dataclass
class Config:
    pass


class Vifs:
    name: str
    parser: str | None = None