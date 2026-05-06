import uuid
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from fastapi import Header, HTTPException
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import models, schemas, crud
from database import SessionLocal, engine
from pdf import generate_pdf
from fastapi.middleware.cors import CORSMiddleware
from typing import cast
import os


# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# AUTH CONFIG
SECRET_KEY = os.getenv("SECRET_KEY") #"supersecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class LoginData(BaseModel):
    username: str
    password: str

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = payload.get("sub")
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_api_key(x_api_key: str = Header(None)):
    return True  # disabled


app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LOGIN
@app.post("/login")
def login(data: LoginData):
    if data.username != "admin" or data.password != "2102":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    token = jwt.encode(
        {"sub": data.username, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {"access_token": token}



models.Base.metadata.create_all(bind=engine)

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# CREATE BILL
@app.post("/bills", response_model=schemas.BillResponse, dependencies=[Depends(get_current_user)])
def create_bill(bill: schemas.BillCreate, db: Session = Depends(get_db)):
    print("CREATE BILL DATA: ", bill)
    return crud.create_bill(db, bill)


# GET ALL
@app.get("/bills", dependencies=[Depends(get_current_user)])
def get_bills(db: Session = Depends(get_db)):
    return db.query(models.Bill).all()


# GET SINGLE
@app.get("/bills/{bill_id}", dependencies=[Depends(get_current_user)])
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.get(models.Bill, bill_id)

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill = cast(models.Bill, bill)

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    items = db.query(models.BillItem).filter_by(bill_id=bill_id).all()

    return {
        "bill": bill,
        "items": items
    }


# UPDATE
@app.put("/bills/{bill_id}", dependencies=[Depends(get_current_user)])
def update_bill(bill_id: int, bill_data: schemas.BillCreate, db: Session = Depends(get_db)):

    bill = db.query(models.Bill).get(bill_id)

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not Found!") #Fix to Raise Exception That Bill Is not Found

    bill.customer = bill_data.customer # type: ignore
    bill.customeradd1 = bill_data.customeradd1 #type: ignore
    bill.customeradd2 = bill_data.customeradd2 #type: ignore
    bill.date = bill_data.date  # type: ignore

    db.query(models.BillItem).filter_by(bill_id=bill_id).delete()

    total = 0

    for item in bill_data.items:
        item_total = item.qty * item.price
        total += item_total

        db_item = models.BillItem(
            bill_id=bill_id,
            description=item.description,
            note=item.note,
            qty=item.qty,
            unit=item.unit,
            price=item.price,
            total=item_total
        )
        db.add(db_item)

    bill.total = round(total, 2)  # type: ignore
    db.commit()

    return bill


# PDF API (UPDATED FOR PERMANENT STORAGE)
@app.get("/bills/{bill_id}/pdf", dependencies=[Depends(get_current_user)])
def get_pdf(bill_id: int, db: Session = Depends(get_db)):
    bill = db.get(models.Bill, bill_id)

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    items = db.query(models.BillItem).filter_by(bill_id=bill_id).all()

    # 🔥 Generate unique file
    # filename = f"{uuid.uuid4()}.pdf"
    filename = f"bill_{bill_id}.pdf"

    # Fix Bill Generation 
    try:
        # Generate PDF locally
        generate_pdf(filename, bill, items)
        print("PDF Generating...")
        print("PDF CREATED:", filename)
    except Exception as e:  #This added 
        print("PDF Generation ERROR:", e)
        raise HTTPException(status_code=500, detail="PDF generation Failed!")
        

    # New Upload to supabase syntax
    # 🔥 FIX: Upload PDF to Supabase
    try:
        with open(filename, "rb") as f:
            supabase.storage.from_("bills").upload(
                filename,
                f,
                {
                    "content-type": "application/pdf",
                    "upsert": "true"
                } #type: ignore
            )

        print("PDF uploaded successfully!")

    except Exception as e:
        print("SUPABASE UPLOAD ERROR:", e)
        raise HTTPException(status_code=500, detail="Supabase upload failed")

    # Added URL ONE
    try:
        public_url = supabase.storage.from_("bills").get_public_url(filename)
    except Exception as e:
        print("URL ERROR:", e)
        raise HTTPException(status_code=500, detail="URL retrieval failed")
    

    # NEW FIX
    try:
        os.remove(filename)
    except:
        pass
    

    return {
        "success": True,
        "message": "PDF GENERATED SUCCESSFULLY !",
        "pdf_url": public_url
    }
# DELETE
@app.delete("/bills/{bill_id}", dependencies=[Depends(get_current_user)])
def delete_bill(bill_id: int, db: Session = Depends(get_db)):

    bill = db.get(models.Bill, bill_id)

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    db.query(models.BillItem).filter_by(bill_id=bill_id).delete()
    db.delete(bill)
    db.commit()

    return {"message": "Deleted"}
