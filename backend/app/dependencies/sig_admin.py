import uuid

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user
from app.repositories import sig_repo


def require_sig_admin(sig_id_param: str = "sig_id"):  # noqa: ARG001
    """Factory that returns a FastAPI dependency enforcing SIG admin access.

    Usage::

        @router.post("/sigs/{sig_id}/forms")
        async def create_form(
            sig_id: uuid.UUID,
            current_user: dict = Depends(require_sig_admin()),
        ):
            ...

    The dependency resolves ``sig_id`` from the path, checks whether the
    authenticated user is a platform admin (SUPER_ADMIN / ADMIN) or holds
    the ADMIN / SUB_ADMIN role inside the given SIG, and raises HTTP 403
    otherwise.  On success it returns the ``current_user`` dict so callers
    can use it directly.
    """

    async def dependency(
        sig_id: uuid.UUID,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        role = current_user.get("role", "")
        if role in ("SUPER_ADMIN", "ADMIN"):
            return current_user

        user_id = uuid.UUID(current_user["sub"])
        member_role = await sig_repo.get_member_role(sig_id, user_id)
        if member_role not in ("ADMIN", "SUB_ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only SIG admins can perform this action.",
            )
        return current_user

    return dependency
