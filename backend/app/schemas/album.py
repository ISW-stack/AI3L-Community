from __future__ import annotations

from pydantic import BaseModel, Field


class AlbumCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)


class AlbumUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)


class AlbumResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    cover_photo_url: str | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    is_archived: bool = False
    photo_count: int = 0
    member_count: int = 0
    created_at: str
    updated_at: str


class AlbumListResponse(BaseModel):
    albums: list[AlbumResponse]
    total: int


class AlbumMemberResponse(BaseModel):
    id: str
    album_id: str
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None = None
    role: str
    status: str
    joined_at: str


class AlbumMemberListResponse(BaseModel):
    members: list[AlbumMemberResponse]
    total: int


class AlbumPhotoResponse(BaseModel):
    id: str
    album_id: str
    uploaded_by: str | None = None
    uploaded_by_name: str | None = None
    storage_url: str | None = None
    thumbnail_url: str | None = None
    original_filename: str | None = None
    file_size_bytes: int = 0
    content_type: str | None = None
    description: str | None = None
    width: int | None = None
    height: int | None = None
    is_zip: bool = False
    created_at: str
    updated_at: str


class AlbumPhotoListResponse(BaseModel):
    photos: list[AlbumPhotoResponse]
    total: int


class AlbumPhotoUpdateRequest(BaseModel):
    description: str | None = Field(None, max_length=2000)


class AlbumAddMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=200)


class AlbumCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    photo_id: str | None = None
    parent_id: str | None = None


class AlbumCommentResponse(BaseModel):
    id: str
    album_id: str
    photo_id: str | None = None
    user_id: str
    display_name: str
    avatar_url: str | None = None
    parent_id: str | None = None
    content: str
    is_deleted: bool = False
    created_at: str
    updated_at: str


class AlbumCommentListResponse(BaseModel):
    comments: list[AlbumCommentResponse]
    total: int
