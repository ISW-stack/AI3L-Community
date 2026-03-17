from pydantic import BaseModel, field_validator


class UserPreferencesResponse(BaseModel):
    theme: str = "light"
    notify_mentions: bool = True
    notify_replies: bool = True
    notify_sig_posts: bool = True
    dm_friends_only: bool = False


class UserPreferencesUpdate(BaseModel):
    theme: str | None = None
    notify_mentions: bool | None = None
    notify_replies: bool | None = None
    notify_sig_posts: bool | None = None
    dm_friends_only: bool | None = None

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str | None) -> str | None:
        if v is not None and v not in ("light", "dark"):
            raise ValueError("theme must be 'light' or 'dark'")
        return v
