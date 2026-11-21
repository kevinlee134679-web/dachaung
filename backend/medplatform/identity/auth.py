from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    account_id: str
    session_hash: str = field(repr=False)
