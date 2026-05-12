from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Boolean
from database import Base

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    customer = Column(String)
    customeradd1 = Column(String, nullable=True)
    customeradd2 = Column(String, nullable=True)
    total = Column(Float)
    date = Column(Date) 
    pdf_url = Column(String, nullable=True)

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
    
    
    # Added 12 may 2026
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="staff")
    is_active = Column(Boolean, default=True)
    
    
# Added 12 may 2026 for admin.html
class ItemMaster(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, unique=True)
    unit = Column(String)
    price = Column(Float)