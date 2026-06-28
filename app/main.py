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
from sqlalchemy import text, func
import app.models.models as models, app.schemas.schemas as schemas, app.services.crud as crud
from app.database.database import SessionLocal, engine
from app.services.pdf import generate_pdf
from fastapi.middleware.cors import CORSMiddleware
from typing import cast
import os


# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://placeholder.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "placeholder-key"
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# AUTH CONFIG
SECRET_KEY = os.getenv("SECRET_KEY") 
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
        tenant_id = payload.get("tenant_id")

        if username is None or tenant_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        return {
            "username": username,
            "role": role,
            "tenant_id": tenant_id
        }

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

# Added 12 may 2026
# Added Require Admin Feature to Enhance Safety and prevent unauthorised changes to configuration files and requirements .
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


def run_startup_migrations():
    db = SessionLocal()
    try:
        # Create settings and customers tables if they don't exist
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_name VARCHAR,
                address1 VARCHAR,
                address2 VARCHAR,
                tenant_id VARCHAR
            );
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS settings (
                id SERIAL PRIMARY KEY,
                company_name VARCHAR,
                address1 VARCHAR,
                address2 VARCHAR,
                phone VARCHAR,
                bank_name VARCHAR,
                account_holder VARCHAR,
                account_number VARCHAR,
                ifsc VARCHAR,
                footer_note VARCHAR,
                show_bank_details BOOLEAN,
                show_footer_note BOOLEAN,
                tenant_id VARCHAR UNIQUE
            );
        """))
        db.commit()

        # Ensure missing columns exist in existing tables
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id VARCHAR;"))
        db.execute(text("ALTER TABLE bills ADD COLUMN IF NOT EXISTS tenant_id VARCHAR;"))
        db.execute(text("ALTER TABLE bills ADD COLUMN IF NOT EXISTS invoice_number INTEGER;"))
        db.execute(text("ALTER TABLE items ADD COLUMN IF NOT EXISTS tenant_id VARCHAR;"))
        db.commit()

        # Ensure columns exist
        try:
            db.execute(text("SELECT tenant_id FROM settings LIMIT 1"))
        except Exception:
            db.rollback()
            db.execute(text("ALTER TABLE settings ADD COLUMN tenant_id VARCHAR UNIQUE;"))
            db.commit()

        try:
            db.execute(text("SELECT tenant_id FROM customers LIMIT 1"))
        except Exception:
            db.rollback()
            db.execute(text("ALTER TABLE customers ADD COLUMN tenant_id VARCHAR;"))
            db.commit()

        # Check if default tenant exists
        default_tenant = db.query(models.Tenant).first()
        if not default_tenant:
            default_tenant = models.Tenant(name="Default Business")
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)

        tenant_id = default_tenant.id

        # Associate settings
        result = db.execute(text("SELECT id FROM settings WHERE tenant_id IS NULL")).fetchall()
        for row in result:
            db.execute(
                text("UPDATE settings SET tenant_id = :tenant_id WHERE id = :id"),
                {"tenant_id": tenant_id, "id": row[0]}
            )
        
        settings_count = db.execute(text("SELECT COUNT(*) FROM settings")).scalar()
        if settings_count == 0:
            db.execute(
                text("""
                    INSERT INTO settings (
                        id, company_name, address1, address2, phone, bank_name,
                        account_holder, account_number, ifsc, footer_note,
                        show_bank_details, show_footer_note, tenant_id
                    ) VALUES (
                        1, 'My Default Company', 'Address Line 1', 'Address Line 2', '0000000000',
                        'Default Bank', 'Holder', '0000000', 'IFSC000', 'Thank you',
                        true, true, :tenant_id
                    )
                """),
                {"tenant_id": tenant_id}
            )
        db.commit()

        # Associate customers, users, items, bills
        db.execute(
            text("UPDATE customers SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": tenant_id}
        )
        db.commit()

        db.query(models.User).filter(models.User.tenant_id == None).update({models.User.tenant_id: tenant_id})
        db.commit()

        db.query(models.ItemMaster).filter(models.ItemMaster.tenant_id == None).update({models.ItemMaster.tenant_id: tenant_id})
        db.commit()

        # Migrate bills and assign invoice_number
        bills = db.query(models.Bill).filter(models.Bill.tenant_id == None).order_by(models.Bill.id.asc()).all()
        if bills:
            for idx, bill in enumerate(bills, start=1):
                bill.tenant_id = tenant_id
                bill.invoice_number = idx
            db.commit()

        # Assign invoice_number to bills without it
        bills_without_invoice = db.query(models.Bill).filter(
            models.Bill.tenant_id == tenant_id,
            models.Bill.invoice_number == None
        ).order_by(models.Bill.id.asc()).all()
        if bills_without_invoice:
            max_inv = db.query(func.max(models.Bill.invoice_number)).filter(
                models.Bill.tenant_id == tenant_id
            ).scalar() or 0
            for idx, bill in enumerate(bills_without_invoice, start=1):
                bill.invoice_number = max_inv + idx
            db.commit()

    except Exception as e:
        db.rollback()
        print("Startup migrations failed:", e)
    finally:
        db.close()


app = FastAPI(
    title="BILLING SOFTWARE BACKEND",
    version="0.0.2",
    description="This is Backend for Developed Business to maintain there bill and create bill, maintain client bills"
    )

# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
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
        role=user.role,
        tenant_id=current_user["tenant_id"]
    )
    db.add(new_user)
    db.commit()
    return {
        "message": "User created successfully"
    }

# =========================
# ADMIN USER MANAGEMENT
# =========================

@app.get(
    "/users",
    dependencies=[Depends(require_admin)]
)
def get_users(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    users = db.query(models.User).filter(models.User.tenant_id == current_user["tenant_id"]).all()

    return [

        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active
        }

        for user in users
    ]


@app.post(
    "/users",
    dependencies=[Depends(require_admin)]
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    existing_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    new_user = models.User(
        username=user.username,
        password=hash_password(user.password),
        role=user.role,
        tenant_id=current_user["tenant_id"],
        is_active=True
    )

    db.add(new_user)

    db.commit()

    return {
        "message": "User created successfully"
    }


@app.put(
    "/users/{user_id}/toggle",
    dependencies=[Depends(require_admin)]
)
def toggle_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.tenant_id == current_user["tenant_id"]
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.is_active = not user.is_active

    db.commit()

    return {
        "message": "User status updated"
    }


@app.delete(
    "/users/{user_id}",
    dependencies=[Depends(require_admin)]
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.tenant_id == current_user["tenant_id"]
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    db.delete(user)

    db.commit()

    return {
        "message": "User deleted"
    }


# =========================
# ITEM MANAGEMENT
# =========================

@app.get(
    "/admin/items",
    dependencies=[Depends(require_admin)]
)
def admin_get_items(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    result = db.execute(
        text("""
            SELECT
                id,
                description,
                unit,
                price
            FROM items
            WHERE tenant_id = :tenant_id
            ORDER BY description
        """),
        {"tenant_id": current_user["tenant_id"]}
    )

    rows = result.fetchall()

    return [

        {
            "id": row[0],
            "description": row[1],
            "unit": row[2],
            "price": float(row[3])
        }

        for row in rows
    ]


@app.post(
    "/admin/items",
    dependencies=[Depends(require_admin)]
)
def create_item(
    item: schemas.ItemCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Check if item description already exists for this tenant to respect UniqueConstraint
    existing = db.execute(
        text("SELECT id FROM items WHERE tenant_id = :tenant_id AND description = :desc"),
        {"tenant_id": current_user["tenant_id"], "desc": item.description}
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Item with this description already exists")

    db.execute(
        text("""
            INSERT INTO items (
                description,
                unit,
                price,
                tenant_id
            )
            VALUES (
                :description,
                :unit,
                :price,
                :tenant_id
            )
        """),
        {
            "description": item.description,
            "unit": item.unit,
            "price": item.price,
            "tenant_id": current_user["tenant_id"]
        }
    )

    db.commit()

    return {
        "message": "Item created"
    }


@app.put(
    "/admin/items/{item_id}",
    dependencies=[Depends(require_admin)]
)
def update_item(
    item_id: int,
    item: schemas.ItemCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Ensure item belongs to tenant
    existing = db.execute(
        text("SELECT id FROM items WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": item_id, "tenant_id": current_user["tenant_id"]}
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")

    db.execute(
        text("""
            UPDATE items
            SET
                description = :description,
                unit = :unit,
                price = :price
            WHERE id = :id AND tenant_id = :tenant_id
        """),
        {
            "id": item_id,
            "description": item.description,
            "unit": item.unit,
            "price": item.price,
            "tenant_id": current_user["tenant_id"]
        }
    )

    db.commit()

    return {
        "message": "Item updated"
    }


@app.delete(
    "/admin/items/{item_id}",
    dependencies=[Depends(require_admin)]
)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Ensure item belongs to tenant
    existing = db.execute(
        text("SELECT id FROM items WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": item_id, "tenant_id": current_user["tenant_id"]}
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")

    db.execute(
        text("""
            DELETE FROM items
            WHERE id = :id AND tenant_id = :tenant_id
        """),
        {
            "id": item_id,
            "tenant_id": current_user["tenant_id"]
        }
    )

    db.commit()

    return {
        "message": "Item deleted"
    }

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
            "tenant_id": user.tenant_id,
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
run_startup_migrations()


# CREATE BILL
@app.post("/bills", response_model=schemas.BillResponse, dependencies=[Depends(get_current_user)])
def create_bill(
    bill: schemas.BillCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    print("CREATE BILL DATA: ", bill)
    return crud.create_bill(db, bill, current_user["tenant_id"])

# Get Customer data
@app.get("/customers")
def get_customers(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = db.execute(
        text("""
            SELECT
                customer_name,
                address1,
                address2
            FROM customers
            WHERE tenant_id = :tenant_id
            ORDER BY customer_name
        """),
        {"tenant_id": current_user["tenant_id"]}
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
def get_items(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = db.execute(
        text("""
            SELECT
                description,
                unit,
                price
            FROM items
            WHERE tenant_id = :tenant_id
            ORDER BY description
        """),
        {"tenant_id": current_user["tenant_id"]}
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
def get_bills(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return db.query(models.Bill).filter(
        models.Bill.tenant_id == current_user["tenant_id"]
    ).order_by(models.Bill.id.asc()).all()

# GET SINGLE
@app.get("/bills/{bill_id}", dependencies=[Depends(get_current_user)])
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    bill = db.query(models.Bill).filter(
        models.Bill.id == bill_id,
        models.Bill.tenant_id == current_user["tenant_id"]
    ).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    items = db.query(models.BillItem).filter_by(bill_id=bill_id).all()

    return {
        "bill": bill,
        "items": items
    }

# UPDATE
@app.put("/bills/{bill_id}", dependencies=[Depends(get_current_user)])
def update_bill(
    bill_id: int,
    bill_data: schemas.BillCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    bill = db.query(models.Bill).filter(
        models.Bill.id == bill_id,
        models.Bill.tenant_id == current_user["tenant_id"]
    ).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not Found!")

    bill.customer = bill_data.customer
    bill.customeradd1 = bill_data.customeradd1
    bill.customeradd2 = bill_data.customeradd2
    bill.date = bill_data.date
    bill.pdf_url = None

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

    bill.total = round(total, 2)
    db.commit()

    return bill

# PDF API (UPDATED FOR PERMANENT STORAGE)
@app.get("/bills/{bill_id}/pdf", dependencies=[Depends(get_current_user)])
def get_pdf(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    bill = db.query(models.Bill).filter(
        models.Bill.id == bill_id,
        models.Bill.tenant_id == current_user["tenant_id"]
    ).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

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
        generate_pdf(filename, bill, items, current_user["tenant_id"])

        print("PDF Generating...")
        print("PDF CREATED:", filename)

    except Exception as e:

        print("PDF Generation ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="PDF generation Failed!"
        )

    # Upload to Supabase under tenant folder prefix
    supabase_path = f"{current_user['tenant_id']}/{filename}"
    try:

        with open(filename, "rb") as f:

            f.seek(0)

            supabase.storage.from_("bills").upload(
                supabase_path,
                f,
                {
                    "content-type": "application/pdf",
                    "upsert": "true"
                }
            )

        print("PDF uploaded successfully!")

    except Exception as e:

        print("SUPABASE UPLOAD ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="Supabase upload failed"
        )

    # Get public URL
    try:

        public_url = supabase.storage.from_("bills").get_public_url(supabase_path)

        # Save PDF URL permanently in DB
        bill.pdf_url = public_url

        db.commit()

    except Exception as e:

        print("URL ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="URL retrieval failed"
        )

    # Delete local temp PDF
    try:
        os.remove(filename)

    except Exception as e:
        print("LOCAL FILE DELETE ERROR:", e)

    # Final response
    return {
        "success": True,
        "message": "PDF GENERATED SUCCESSFULLY!",
        "pdf_url": public_url
    }


# DELETE
@app.delete("/bills/{bill_id}", dependencies=[Depends(get_current_user)])
def delete_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    bill = db.query(models.Bill).filter(
        models.Bill.id == bill_id,
        models.Bill.tenant_id == current_user["tenant_id"]
    ).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    db.query(models.BillItem).filter_by(bill_id=bill_id).delete()

    db.delete(bill)

    db.commit()

    return {"message": "Deleted"}

# =========================
# SETTINGS MANAGEMENT
# =========================

@app.get(
    "/admin/settings",
    dependencies=[Depends(require_admin)]
)
def get_settings(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    result = db.execute(
        text("""
            SELECT *
            FROM settings
            WHERE tenant_id = :tenant_id
            LIMIT 1
        """),
        {"tenant_id": current_user["tenant_id"]}
    )

    row = result.fetchone()

    if not row:
        return {}

    return {

        "id": row[0],
        "company_name": row[1],
        "address1": row[2],
        "address2": row[3],
        "phone": row[4],
        "bank_name": row[5],
        "account_holder": row[6],
        "account_number": row[7],
        "ifsc": row[8],
        "footer_note": row[9],
        "show_bank_details": row[10],
        "show_footer_note": row[11]
    }


@app.put(
    "/admin/settings",
    dependencies=[Depends(require_admin)]
)
def update_settings(
    data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    db.execute(
        text("""
            UPDATE settings

            SET

                company_name = :company_name,
                address1 = :address1,
                address2 = :address2,
                phone = :phone,
                bank_name = :bank_name,
                account_holder = :account_holder,
                account_number = :account_number,
                ifsc = :ifsc,
                footer_note = :footer_note,
                show_bank_details = :show_bank_details,
                show_footer_note = :show_footer_note

            WHERE tenant_id = :tenant_id
        """),
        {**data, "tenant_id": current_user["tenant_id"]}
    )

    db.commit()

    return {
        "message": "Settings updated"
    }
