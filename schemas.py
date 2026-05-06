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
    date: date
    items: List[Item]
    
class BillResponse(BaseModel):
    id: int
    customer: str
    total: float
    
    class Config:
        orm_mode = True
        