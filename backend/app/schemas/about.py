from pydantic import BaseModel


class ContributorResponse(BaseModel):
    id: int
    display_name: str
    role: str
    avatar_url: str


class ContributorsListResponse(BaseModel):
    contributors: list[ContributorResponse]
