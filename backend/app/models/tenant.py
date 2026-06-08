from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Organization(BaseModel):
    __tablename__ = "organizations"

    name = Column(String, nullable=False)
    domain = Column(String, unique=True, index=True)
    
    # Relationships
    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="organization", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="organization", cascade="all, delete-orphan")

class User(BaseModel):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    is_active = Column(Boolean, default=True)

    # Relationships
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

class Membership(BaseModel):
    __tablename__ = "memberships"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False, default="member") # admin, member, owner

    # Relationships
    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")

class APIKey(BaseModel):
    __tablename__ = "api_keys"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    is_active = Column(Boolean, default=True)

    organization = relationship("Organization", back_populates="api_keys")

class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan_name = Column(String, nullable=False, default="free")
    status = Column(String, nullable=False, default="active")
    stripe_customer_id = Column(String)
    stripe_subscription_id = Column(String)

    organization = relationship("Organization", back_populates="subscriptions")

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False) # e.g. "user.created", "campaign.started"
    resource_type = Column(String, nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_json = Column(JSON, default={})

    organization = relationship("Organization", back_populates="audit_logs")
