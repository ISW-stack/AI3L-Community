"""Activity Albums endpoints."""

import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, Query, UploadFile, status

from app.core.constants import (
    DEFAULT_PAGE_SIZE_ALBUM_COMMENTS,
    DEFAULT_PAGE_SIZE_ALBUM_PHOTOS,
    DEFAULT_PAGE_SIZE_ALBUMS,
    MAX_ALBUM_UPLOAD_BYTES,
    MAX_PAGE_NUMBER,
    MAX_PAGE_SIZE,
    RATE_LIMIT_ALBUM_COMMENT,
    RATE_LIMIT_ALBUM_UPLOAD,
)
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.schemas.album import (
    AlbumCommentCreateRequest,
    AlbumCommentListResponse,
    AlbumCommentResponse,
    AlbumCreateRequest,
    AlbumListResponse,
    AlbumMemberListResponse,
    AlbumPhotoListResponse,
    AlbumPhotoResponse,
    AlbumPhotoUpdateRequest,
    AlbumResponse,
    AlbumUpdateRequest,
)
from app.services.album import (
    add_member,
    approve_member,
    create_album,
    create_comment,
    delete_album,
    delete_comment,
    delete_photo,
    get_album,
    get_photo,
    join_album,
    list_albums,
    list_comments,
    list_members,
    list_photos,
    remove_member,
    update_album,
    update_photo,
    upload_file_zip,
    upload_photo,
)

router = APIRouter(prefix="/albums", tags=["albums"])


# ── Album CRUD ──────────────────────────────────────────────────────────────


@router.post("", response_model=AlbumResponse, status_code=status.HTTP_201_CREATED)
async def create_album_endpoint(
    req: AlbumCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> AlbumResponse:
    album = await create_album(
        title=req.title,
        description=req.description,
        user_id=current_user["sub"],
    )
    return AlbumResponse(**album)


@router.get("", response_model=AlbumListResponse)
async def list_albums_endpoint(
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_ALBUMS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(get_current_user),
) -> AlbumListResponse:
    albums, total = await list_albums(page=page, page_size=page_size, viewer_id=current_user["sub"])
    return AlbumListResponse(albums=cast(list[Any], albums), total=total)


@router.get("/{album_id}", response_model=AlbumResponse)
async def get_album_endpoint(
    album_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> AlbumResponse:
    album = await get_album(str(album_id))
    return AlbumResponse(**album)


@router.put("/{album_id}", response_model=AlbumResponse)
async def update_album_endpoint(
    album_id: uuid.UUID,
    req: AlbumUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> AlbumResponse:
    album = await update_album(
        album_id=str(album_id),
        user_id=current_user["sub"],
        user_role=current_user["role"],
        title=req.title,
        description=req.description,
    )
    return AlbumResponse(**album)


@router.delete("/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_album_endpoint(
    album_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    deleted = await delete_album(
        album_id=str(album_id),
        user_id=current_user["sub"],
        user_role=current_user["role"],
    )
    if not deleted:
        raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")


# ── Members ─────────────────────────────────────────────────────────────────


@router.post("/{album_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member_endpoint(
    album_id: uuid.UUID,
    target_user_id: str = Query(..., description="User ID to add"),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    result = await add_member(
        album_id=str(album_id),
        user_id=current_user["sub"],
        target_user_id=target_user_id,
        user_role=current_user["role"],
    )
    return result


@router.post("/{album_id}/join", status_code=status.HTTP_201_CREATED)
async def join_album_endpoint(
    album_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    result = await join_album(
        album_id=str(album_id),
        user_id=current_user["sub"],
    )
    return result


@router.put("/{album_id}/members/{member_id}/approve")
async def approve_member_endpoint(
    album_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    approved = await approve_member(
        album_id=str(album_id),
        user_id=current_user["sub"],
        member_id=str(member_id),
        user_role=current_user["role"],
    )
    if not approved:
        raise AppError(ErrorCode.ALBUM_001, 404, "Member not found.")
    return {"approved": True}


@router.delete("/{album_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_endpoint(
    album_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    removed = await remove_member(
        album_id=str(album_id),
        user_id=current_user["sub"],
        target_user_id=str(user_id),
        user_role=current_user["role"],
    )
    if not removed:
        raise AppError(ErrorCode.ALBUM_001, 404, "Member not found.")


@router.get("/{album_id}/members", response_model=AlbumMemberListResponse)
async def list_members_endpoint(
    album_id: uuid.UUID,
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(get_current_user),
) -> AlbumMemberListResponse:
    members, total = await list_members(
        album_id=str(album_id),
        page=page,
        page_size=page_size,
    )
    return AlbumMemberListResponse(members=cast(list[Any], members), total=total)


# ── Photos ──────────────────────────────────────────────────────────────────


@router.post(
    "/{album_id}/photos", response_model=AlbumPhotoResponse, status_code=status.HTTP_201_CREATED
)
async def upload_photo_endpoint(
    album_id: uuid.UUID,
    file: UploadFile,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> AlbumPhotoResponse:
    if not await check_rate_limit(
        f"rl:album_upload:{current_user['sub']}", *RATE_LIMIT_ALBUM_UPLOAD
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Upload rate limit exceeded.")

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(8192):
        total += len(chunk)
        if total > MAX_ALBUM_UPLOAD_BYTES:
            raise AppError(ErrorCode.SYS_422, 413, "File too large.")
        chunks.append(chunk)
    file_data = b"".join(chunks)
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    photo = await upload_photo(
        album_id=str(album_id),
        user_id=current_user["sub"],
        file_data=file_data,
        filename=filename,
        content_type=content_type,
    )
    return AlbumPhotoResponse(**photo)


@router.post(
    "/{album_id}/files", response_model=AlbumPhotoResponse, status_code=status.HTTP_201_CREATED
)
async def upload_file_endpoint(
    album_id: uuid.UUID,
    file: UploadFile,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> AlbumPhotoResponse:
    if not await check_rate_limit(
        f"rl:album_upload:{current_user['sub']}", *RATE_LIMIT_ALBUM_UPLOAD
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Upload rate limit exceeded.")

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(8192):
        total += len(chunk)
        if total > MAX_ALBUM_UPLOAD_BYTES:
            raise AppError(ErrorCode.SYS_422, 413, "File too large.")
        chunks.append(chunk)
    file_data = b"".join(chunks)
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown.zip"

    result = await upload_file_zip(
        album_id=str(album_id),
        user_id=current_user["sub"],
        file_data=file_data,
        filename=filename,
        content_type=content_type,
    )
    return AlbumPhotoResponse(**result)


@router.get("/{album_id}/photos", response_model=AlbumPhotoListResponse)
async def list_photos_endpoint(
    album_id: uuid.UUID,
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_ALBUM_PHOTOS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(get_current_user),
) -> AlbumPhotoListResponse:
    photos, total = await list_photos(
        album_id=str(album_id),
        page=page,
        page_size=page_size,
        viewer_id=current_user["sub"],
    )
    return AlbumPhotoListResponse(photos=cast(list[Any], photos), total=total)


@router.get("/{album_id}/photos/{photo_id}", response_model=AlbumPhotoResponse)
async def get_photo_endpoint(
    album_id: uuid.UUID,
    photo_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> AlbumPhotoResponse:
    photo = await get_photo(album_id=str(album_id), photo_id=str(photo_id))
    return AlbumPhotoResponse(**photo)


@router.put("/{album_id}/photos/{photo_id}", response_model=AlbumPhotoResponse)
async def update_photo_endpoint(
    album_id: uuid.UUID,
    photo_id: uuid.UUID,
    req: AlbumPhotoUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> AlbumPhotoResponse:
    photo = await update_photo(
        album_id=str(album_id),
        photo_id=str(photo_id),
        user_id=current_user["sub"],
        user_role=current_user["role"],
        description=req.description,
    )
    return AlbumPhotoResponse(**photo)


@router.delete("/{album_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo_endpoint(
    album_id: uuid.UUID,
    photo_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    deleted = await delete_photo(
        album_id=str(album_id),
        photo_id=str(photo_id),
        user_id=current_user["sub"],
        user_role=current_user["role"],
    )
    if not deleted:
        raise AppError(ErrorCode.ALBUM_001, 404, "Photo not found.")


# ── Comments ────────────────────────────────────────────────────────────────


@router.post(
    "/{album_id}/comments", response_model=AlbumCommentResponse, status_code=status.HTTP_201_CREATED
)
async def create_comment_endpoint(
    album_id: uuid.UUID,
    req: AlbumCommentCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> AlbumCommentResponse:
    if not await check_rate_limit(
        f"rl:album_comment:{current_user['sub']}", *RATE_LIMIT_ALBUM_COMMENT
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Comment rate limit exceeded.")

    comment = await create_comment(
        album_id=str(album_id),
        user_id=current_user["sub"],
        content=req.content,
        photo_id=req.photo_id,
        parent_id=req.parent_id,
    )
    return AlbumCommentResponse(**comment)


@router.get("/{album_id}/comments", response_model=AlbumCommentListResponse)
async def list_comments_endpoint(
    album_id: uuid.UUID,
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_ALBUM_COMMENTS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(get_current_user),
) -> AlbumCommentListResponse:
    comments, total = await list_comments(
        album_id=str(album_id),
        page=page,
        page_size=page_size,
        viewer_id=current_user["sub"],
    )
    return AlbumCommentListResponse(comments=cast(list[Any], comments), total=total)


@router.delete("/{album_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment_endpoint(
    album_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    deleted = await delete_comment(
        album_id=str(album_id),
        comment_id=str(comment_id),
        user_id=current_user["sub"],
        user_role=current_user["role"],
    )
    if not deleted:
        raise AppError(ErrorCode.ALBUM_001, 404, "Comment not found.")
