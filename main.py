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
from sqlalchemy import text
import models, schemas, crud
from database import SessionLocal, engine
from pdf import generate_pdf
from fastapi.middleware.cors import CORSMiddleware
from typing import cast
import os


# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") 
# ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
# ADMIN_PASS = os.getenv("ADMIN_PASSWORD")
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# AUTH CONFIG
SECRET_KEY = os.getenv("SECRET_KEY") #"supersecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class LoginData(BaseModel):
    username: str
    password: str
    
# Added 12 may 2026 (45 to 59) line
# HASH PASSWORD
def hash_password(password: str):
    return pwd_context.hash(password)


# VERIFY PASSWORD
def verify_password(
    plain_password,
    hashed_password
):
    return pwd_context.verify(
        plain_password,
        hashed_password
    )

# def get_current_user(token: str = Depends(oauth2_scheme)):
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         user = payload.get("sub")
#         if user is None:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return user
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# Added 12 may 2026
def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")
        role = payload.get("role")

        if username is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        return {
            "username": username,
            "role": role
        }

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

# Added 12 may 2026

def require_admin(
    current_user = Depends(get_current_user)
):

    if current_user["role"] != "admin":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user

def verify_api_key(x_api_key: str = Header(None)):
    return True  # disabled


app = FastAPI()

# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Added 12 may 2026 
# REGISTER USER
@app.post("/register", dependencies=[Depends(require_admin)])
def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )
        
    hashed_password = hash_password(
        user.password
    )
    
    new_user = models.User(
        username=user.username,
        password=hashed_password,
        role=user.role
    )
    db.add(new_user)
    db.commit()
    return {
        "message": "User created successfully"
    }

# LOGIN
# @app.post("/login")
# def login(data: LoginData):
#     if data.username != ADMIN_USERNAME or data.password != ADMIN_PASS:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

#     # Checking whether SECRET KEY is Present or Not !
#     if not SECRET_KEY:
#         raise HTTPException(status_code=500, detail="SECRET_KEY missing")

#     token = jwt.encode(
#         {"sub": data.username, "exp": expire},
#         SECRET_KEY,
#         algorithm=ALGORITHM
#     )

#     # Feature added 12 may 26
#     return {
#         "access_token": token,
#         "token-type": "bearer",
#         "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
#     }

# Added 12 may 2026 
@app.post("/login")
def login(
    data: schemas.UserLogin,
    db: Session = Depends(get_db)
):

    user = db.query(models.User).filter(
        models.User.username == data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        data.password,
        user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User disabled"
        )

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    token = jwt.encode(
        {
            "sub": user.username,
            "role": user.role,
            "exp": expire
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


models.Base.metadata.create_all(bind=engine)


# CREATE BILL
@app.post("/bills", response_model=schemas.BillResponse, dependencies=[Depends(get_current_user)])
def create_bill(bill: schemas.BillCreate, db: Session = Depends(get_db)):
    print("CREATE BILL DATA: ", bill)
    return crud.create_bill(db, bill)

# Get Customer data
@app.get("/customers")
def get_customers(db: Session = Depends(get_db)):
    result = db.execute(

        text("""
            SELECT
                customer_name,
                address1,
                address2
            FROM customers
            ORDER BY customer_name
        """)
    )

    rows = result.fetchall()

    return [

        {
            "customer_name": row[0],
            "address1": row[1],
            "address2": row[2]
        }

        for row in rows
    ]
    
# Get Customer Items
@app.get("/items")
def get_items(db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            SELECT
                description,
                unit,
                price
            FROM items
            ORDER BY description
        """)
    )
    rows = result.fetchall()

    return [
        {
            "description": row[0],
            "unit": row[1],
            "price": float(row[2])
        }
        for row in rows
    ]

#GET ALL
@app.get("/bills", dependencies=[Depends(get_current_user)])
def get_bills(db: Session = Depends(get_db)):
    return db.query(models.Bill).order_by(models.Bill.id.asc()).all()

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

    # bill = db.query(models.Bill).get(bill_id)
    bill = db.get(models.Bill, bill_id)

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not Found!") #Fix to Raise Exception That Bill Is not Found

    bill.customer = bill_data.customer # type: ignore
    bill.customeradd1 = bill_data.customeradd1 #type: ignore
    bill.customeradd2 = bill_data.customeradd2 #type: ignore
    bill.date = bill_data.date  # type: ignore
    bill.pdf_url = None #type: ignore

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

    # ADDED: Return existing PDF if already generated
    if bill.pdf_url:
        return {
            "success": True,
            "message": "Existing PDF loaded successfully!",
            "pdf_url": bill.pdf_url
        }

    items = db.query(models.BillItem).filter_by(bill_id=bill_id).all()

    # Generate unique file name to prevent unauthorized access
    filename = f"bill_{bill_id}_{uuid.uuid4().hex}.pdf"


    # PDF GENERATION
    try:

        # Generate PDF locally
        generate_pdf(filename, bill, items)

        print("PDF Generating...")
        print("PDF CREATED:", filename)

    except Exception as e:

        print("PDF Generation ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="PDF generation Failed!"
        )

    # Upload to Supabase
    try:

        with open(filename, "rb") as f:

            f.seek(0)

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

        raise HTTPException(
            status_code=500,
            detail="Supabase upload failed"
        )

    # 🔥 Get public URL
    try:

        public_url = supabase.storage.from_("bills").get_public_url(filename)

        # 🔥 ADDED: Save PDF URL permanently in DB
        bill.pdf_url = public_url #type: ignore

        db.commit()

    except Exception as e:

        print("URL ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="URL retrieval failed"
        )

    # 🔥 Delete local temp PDF
    try:
        os.remove(filename)

    except Exception as e:
        print("LOCAL FILE DELETE ERROR:", e)

    # 🔥 Final response
    return {
        "success": True,
        "message": "PDF GENERATED SUCCESSFULLY!",
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
