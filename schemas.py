from pydantic import BaseModel
from typing import List
from datetime import date

class Item(BaseModel):
    description: str
    note: str | None = None
    qty: float
    unit: str   #Sqft, Meter,Quantity etc
    price: float

class BillCreate(BaseModel):
    customer: str
    customeradd1: str | None = None
    customeradd2: str | None = None
    date: date
    items: List[Item]
    
class BillResponse(BaseModel):
    id: int
    customer: str
    total: float
    
    class Config:
        # orm_mode = True
        from_attributes = True
        