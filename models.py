from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date
from database import Base

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    customer = Column(String)
    total = Column(Float)
    date = Column(Date) 

class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"))
    description = Column(String)
    note = Column(String)
    qty = Column(Integer)
    unit = Column(String)
    price = Column(Float)
    total = Column(Float)