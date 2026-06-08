from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    developer = "developer"
    manager = "manager"
    tech_lead = "tech_lead"


class TokenPayload(BaseModel):
    developer_id: str
    team_id: str = "default"
    role: Role = Role.developer


class TokenRequest(BaseModel):
    developer_id: str
    team_id: str = "default"
    role: Role = Role.developer


class TokenResponse(BaseModel):
    token: str
    expires_in: int
