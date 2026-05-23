from sqlalchemy import Column, String, Float, Integer, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import relationship
import time
from backend.database.core import Base

class Project(Base):
    __tablename__ = "projects"

    project_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    root_path = Column(String, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(Float, default=lambda: time.time())
    updated_at = Column(Float, default=lambda: time.time(), onupdate=lambda: time.time())
    notes = Column(Text, nullable=True)
    # Using JSON column for metadata dictionary
    meta_data = Column("metadata", JSON, nullable=True)
    
    # Relationship to Jobs
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    # Note: adding project_id explicitly to unify job per-project SQLite into the global SQLite.
    project_id = Column(String, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    image_path = Column(String, nullable=False)
    source_pdf_path = Column(String, nullable=True)
    compressed_pdf_path = Column(String, nullable=True)
    status = Column(String, nullable=False, index=True)
    pdf_status = Column(String, nullable=True, index=True)
    pdf_commands_json = Column(Text, nullable=True)
    
    # Legacy payload column kept for backward compatibility with older tests/tools.
    vlm_result_json = Column(Text, nullable=True)

    # Immutable raw VLM result kept for audit/reference only.
    vlm_raw_json = Column(Text, nullable=True)
    vlm_stats = Column(Text, nullable=True)
    validation_json = Column(Text, nullable=True)

    # Normalized header/summary fields (single source of truth for UI/export assembly).
    voucher_id = Column(String, nullable=True)
    purpose = Column(String, nullable=True)
    supplier = Column(String, nullable=True)
    invoice_date = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)
    
    qr_verified = Column(Integer, default=0)

    # Legacy manual payload column kept for backward compatibility.
    manual_json_text = Column(Text, nullable=True)
    manual_updated_at = Column(Float, nullable=True)

    # Asset metadata — populated after split/ingest and preview cache generation.
    source_format = Column(String, nullable=True)   # e.g. "jpg", "jxl", "png"
    preview_cache_path = Column(String, nullable=True)  # abs path to the latest preview cache file



    created_at = Column(Float, default=lambda: time.time())
    updated_at = Column(Float, default=lambda: time.time(), onupdate=lambda: time.time())
    
    # Relationships
    project = relationship("Project", back_populates="jobs")
    items = relationship("InvoiceItem", back_populates="job", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="job", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=True)
    description = Column(String, nullable=True)
    quantity = Column(Float, nullable=True)    # Float for fractional quantities
    price = Column(Float, nullable=True)
    total = Column(Float, nullable=True)
    remark = Column(String, nullable=True)
    
    # Relationship
    job = relationship("Job", back_populates="items")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=True, index=True)
    event_type = Column(String, nullable=True)
    ts = Column(Float, default=lambda: time.time())
    payload = Column(Text, nullable=True)  # JSON Payload stored as String
    
    # Relationship
    job = relationship("Job", back_populates="events")


class Person(Base):
    """表示人員或虛擬實體（如虛擬印章持有者）"""
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False)  # handler, activity_general_affairs, general_affairs_head, president, advisor, fin_original, fin_audited, club_seal
    is_virtual = Column(Boolean, default=False)  # True 表示虛擬實體（社團大章、財務章等）
    created_at = Column(Float, default=lambda: time.time())
    
    # Relationship
    stamps = relationship("Stamp", back_populates="owner", cascade="all, delete-orphan")


# DEPRECATED: Group 模型已廢棄，保留用於向後兼容性
# 新系統應使用 Person 模型代替
class Group(Base):
    """
    [DEPRECATED] 舊版 Group 模型
    
    v0.0.20 起，應使用 Person 模型代替。
    此模型僅保留以支持向後相容性，未來版本將移除。
    """
    __tablename__ = "groups"

    group_name = Column(String, primary_key=True)
    leader_name = Column(String, nullable=True)


class Stamp(Base):
    __tablename__ = "stamps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, default="personal")  # 簡化為統一 personal，位置由 Person.role 決定
    image_path = Column(String, nullable=False)
    created_at = Column(Float, default=lambda: time.time())
    
    # Relationship
    owner = relationship("Person", back_populates="stamps")


class Suggestion(Base):
    __tablename__ = "suggestions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, nullable=False, index=True)
    value = Column(String, nullable=False)
    count = Column(Integer, default=1)
    last_used_at = Column(Float, default=lambda: time.time())
    
    # To enforce unique constraint per category and value
    __table_args__ = (
        {"sqlite_autoincrement": True} # Just declaring it for completeness
    )
