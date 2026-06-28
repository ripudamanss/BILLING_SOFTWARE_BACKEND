from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Boolean, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database.database import Base
import uuid

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)  # Nullable for migration compatibility
    invoice_number = Column(Integer, nullable=True)                     # Nullable for migration compatibility
    customer = Column(String)
    customeradd1 = Column(String, nullable=True)
    customeradd2 = Column(String, nullable=True)
    total = Column(Float)
    date = Column(Date) 
    pdf_url = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'invoice_number', name='_tenant_invoice_uc'),
    )

class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"))
    description = Column(String)
    note = Column(String)
    qty = Column(Float)
    unit = Column(String)
    price = Column(Float)
    total = Column(Float)
    
    
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)  # Nullable for migration compatibility
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="staff")
    is_active = Column(Boolean, default=True)
    
    
class ItemMaster(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)  # Nullable for migration compatibility
    description = Column(String)
    unit = Column(String)
    price = Column(Float)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'description', name='_tenant_item_description_uc'),
    )