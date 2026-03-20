from pydantic import BaseModel, Field


class OrgChartMemberResponse(BaseModel):
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None = None
    role: str
    org_chart_bio: str | None = None


class OrgChartSigResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    org_chart_description: str | None = None
    member_count: int
    members: list[OrgChartMemberResponse]
    override: "OrgChartOverrideResponse | None" = None


class OrgChartCategoryResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    creator_id: str | None = None
    creator_display_name: str | None = None
    creator_avatar_url: str | None = None
    override: "OrgChartOverrideResponse | None" = None


class OrgChartOverrideResponse(BaseModel):
    entity_type: str
    entity_id: str
    custom_title: str | None = None
    custom_description: str | None = None
    display_order: int = 0
    is_visible: bool = True


class OrgChartResponse(BaseModel):
    sigs: list[OrgChartSigResponse]
    categories: list[OrgChartCategoryResponse]


class OrgChartOverrideUpdateRequest(BaseModel):
    custom_title: str | None = Field(None, max_length=200)
    custom_description: str | None = Field(None, max_length=2000)
    display_order: int | None = None
    is_visible: bool | None = None


class SigOrgChartDescriptionUpdateRequest(BaseModel):
    org_chart_description: str | None = Field(None, max_length=1000)


class MemberOrgChartBioUpdateRequest(BaseModel):
    org_chart_bio: str | None = Field(None, max_length=500)


class MembersListResponse(BaseModel):
    members: list["MemberCardResponse"]
    total: int


class MemberCardResponse(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    role: str
    affiliation: str | None = None
    bio: str | None = None
