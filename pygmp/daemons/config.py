from dataclasses import dataclass


@dataclass
class Config:
    pass


class Vifs:
    name: str
    address: str | None = None