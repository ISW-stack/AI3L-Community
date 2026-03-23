"""
Tests for DM UX fixes (L-18 removed dm_friends_only from PublicUserResponse).

All tests that asserted dm_friends_only in PublicUserResponse, converter output,
or the GET /users/{id} endpoint have been removed because the field was
intentionally stripped for privacy (L-18 fix).
"""
