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
    invoice_number: int | None = None
    customer: str
    total: float
    
    class Config:
        from_attributes = True
        
# Added 12 may 2026
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "staff"


class UserLogin(BaseModel):
    username: str
    password: str
    
    
# Added 12 may 2026 For admin.html
class ItemCreate(BaseModel):
    description: str
    unit: str
    price: float


class ItemResponse(BaseModel):
    id: int
    description: str
    unit: str
    price: float

    class Config:
        from_attributes = True