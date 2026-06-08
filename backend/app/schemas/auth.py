from enum import Enum
from pydantic import BaseModel


class Role(str, Enum):
    developer = "developer"
    manager = "manager"
    tech_lead = "tech_lead"


class TokenPayload(BaseModel):
    developer_id: str
    team_id: str = "default"
    role: Role = Role.developer
