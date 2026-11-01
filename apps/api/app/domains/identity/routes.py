from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent, Membership, Organization, OrganizationInvitation, User, now
from app.db.session import get_session
from app.dependencies import current_user, require_membership

router = APIRouter(tags=["identity", "organizations"])


class InvitationCreate(BaseModel):
    email: EmailStr
    role: Literal["admin", "member", "viewer"] = "member"


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class MembershipRoleUpdate(BaseModel):
    role: Literal["admin", "member", "viewer"]


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def _require_org_admin(org_id: str, user: User, session: AsyncSession) -> Membership:
    membership = await require_membership(org_id, user, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Organization administrator role required")
    return membership


@router.post("/organizations/{organization_id}/invitations", status_code=201)
async def create_invitation(
    organization_id: str,
    body: InvitationCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    actor = await _require_org_admin(organization_id, user, session)
    if actor.role == "admin" and body.role == "admin":
        raise HTTPException(403, "Only an organization owner can invite administrators")
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    email = str(body.email).strip().lower()
    invited_user = await session.scalar(select(User).where(User.email == email))
    if invited_user is not None:
        existing = await session.scalar(
            select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == invited_user.id)
        )
        if existing is not None:
            raise HTTPException(409, "User is already a member of this organization")
    # Serialize invitations for one organization on PostgreSQL so concurrent
    # requests cannot create multiple live invitations for the same address.
    await session.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
    previous = await session.scalar(
        select(OrganizationInvitation)
        .where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.email == email,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if previous is not None:
        previous.revoked_at = now()
    token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation(
        id=uuid4().hex,
        organization_id=organization_id,
        email=email,
        role=body.role,
        token_hash=_token_digest(token),
        created_by=user.id,
        expires_at=now() + timedelta(days=7),
    )
    session.add(invitation)
    session.add(AuditEvent(
        organization_id=organization_id,
        actor_user_id=user.id,
        action="ORGANIZATION_INVITATION_CREATED",
        resource_type="organization_invitation",
        resource_id=invitation.id,
        metadata_json={"email": email, "role": body.role},
    ))
    await session.commit()
    return {
        "id": invitation.id,
        "email": invitation.email,
        "role": invitation.role,
        "token": token,
        "accept_path": "/invite/accept?token=" + token,
        "expires_at": invitation.expires_at.isoformat(),
    }


@router.get("/organizations/{organization_id}/invitations")
async def list_invitations(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    await _require_org_admin(organization_id, user, session)
    rows = await session.scalars(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.organization_id == organization_id)
        .order_by(OrganizationInvitation.created_at.desc())
    )
    result = []
    current_time = now()
    for item in rows.all():
        if item.accepted_at is not None:
            state = "ACCEPTED"
        elif item.revoked_at is not None:
            state = "REVOKED"
        elif _utc(item.expires_at) <= current_time:
            state = "EXPIRED"
        else:
            state = "PENDING"
        result.append({"id": item.id, "email": item.email, "role": item.role, "status": state,
                       "created_at": item.created_at.isoformat(), "expires_at": item.expires_at.isoformat()})
    return result


@router.delete("/organizations/{organization_id}/invitations/{invitation_id}")
async def revoke_invitation(
    organization_id: str,
    invitation_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    await _require_org_admin(organization_id, user, session)
    invitation = await session.scalar(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.id == invitation_id, OrganizationInvitation.organization_id == organization_id)
        .with_for_update()
    )
    if invitation is None:
        raise HTTPException(404, "Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(409, "Accepted invitations cannot be revoked")
    if invitation.revoked_at is None:
        invitation.revoked_at = now()
        session.add(AuditEvent(organization_id=organization_id, actor_user_id=user.id,
            action="ORGANIZATION_INVITATION_REVOKED", resource_type="organization_invitation",
            resource_id=invitation.id, metadata_json={"email": invitation.email}))
        await session.commit()
    return {"revoked": True}


@router.post("/invitations/accept")
async def accept_invitation(
    body: InvitationAccept,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    invitation = await session.scalar(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.token_hash == _token_digest(body.token))
        .with_for_update()
    )
    if invitation is None or invitation.revoked_at is not None or invitation.accepted_at is not None:
        raise HTTPException(400, "Invitation is invalid, expired, or already used")
    if _utc(invitation.expires_at) <= now():
        raise HTTPException(400, "Invitation is invalid, expired, or already used")
    if user.email.strip().lower() != invitation.email:
        raise HTTPException(403, "Invitation was issued to a different email address")
    inviter_membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == invitation.organization_id,
            Membership.user_id == invitation.created_by,
        )
    )
    if inviter_membership is None or inviter_membership.role not in {"owner", "admin"}:
        invitation.revoked_at = now()
        await session.commit()
        raise HTTPException(400, "Invitation is no longer valid")
    existing = await session.scalar(
        select(Membership).where(Membership.organization_id == invitation.organization_id, Membership.user_id == user.id)
    )
    if existing is not None:
        raise HTTPException(409, "User is already a member of this organization")
    invitation.accepted_at = now()
    membership = Membership(id=uuid4().hex, organization_id=invitation.organization_id, user_id=user.id, role=invitation.role)
    session.add(membership)
    session.add(AuditEvent(organization_id=invitation.organization_id, actor_user_id=user.id,
        action="ORGANIZATION_INVITATION_ACCEPTED", resource_type="organization_membership",
        resource_id=membership.id, metadata_json={"invitation_id": invitation.id, "role": invitation.role}))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "User is already a member of this organization") from None
    return {"organization_id": invitation.organization_id, "role": invitation.role, "joined": True}


@router.get("/organizations/{organization_id}/members")
async def list_members(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    await require_membership(organization_id, user, session)
    rows = await session.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization_id).order_by(Membership.created_at, User.email)
    )
    return [{"user_id": membership.user_id, "email": member.email, "name": member.name,
             "role": membership.role, "joined_at": membership.created_at.isoformat()}
            for membership, member in rows.all()]


@router.patch("/organizations/{organization_id}/members/{member_user_id}")
async def update_member_role(
    organization_id: str,
    member_user_id: str,
    body: MembershipRoleUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    actor = await _require_org_admin(organization_id, user, session)
    target = await session.scalar(
        select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == member_user_id).with_for_update()
    )
    if target is None:
        raise HTTPException(404, "Organization member not found")
    if target.role == "owner":
        raise HTTPException(409, "Transfer ownership before changing or removing the owner")
    if actor.role == "admin" and target.role == "admin":
        raise HTTPException(403, "Administrators cannot change another administrator")
    if actor.role == "admin" and body.role == "admin":
        raise HTTPException(403, "Only an organization owner can grant administrator role")
    previous_role = target.role
    target.role = body.role
    session.add(AuditEvent(organization_id=organization_id, actor_user_id=user.id,
        action="ORGANIZATION_MEMBER_ROLE_CHANGED", resource_type="organization_membership",
        resource_id=target.id, metadata_json={"user_id": member_user_id, "from": previous_role, "to": body.role}))
    await session.commit()
    return {"user_id": member_user_id, "role": target.role}


@router.delete("/organizations/{organization_id}/members/{member_user_id}")
async def remove_member(
    organization_id: str,
    member_user_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    actor = await _require_org_admin(organization_id, user, session)
    target = await session.scalar(
        select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == member_user_id).with_for_update()
    )
    if target is None:
        raise HTTPException(404, "Organization member not found")
    if target.role == "owner":
        raise HTTPException(409, "Transfer ownership before removing the owner")
    if actor.role == "admin" and target.role == "admin":
        raise HTTPException(403, "Administrators cannot remove another administrator")
    session.add(AuditEvent(organization_id=organization_id, actor_user_id=user.id,
        action="ORGANIZATION_MEMBER_REMOVED", resource_type="organization_membership",
        resource_id=target.id, metadata_json={"user_id": member_user_id, "role": target.role}))
    await session.delete(target)
    await session.commit()
    return {"removed": True}
