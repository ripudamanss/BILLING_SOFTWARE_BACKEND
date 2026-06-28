from sqlalchemy import text, func
from sqlalchemy.orm import Session
import app.models.models as models

def create_bill(db: Session, bill_data, tenant_id: str):

    total = 0

    # ------------------------
    # CREATE MAIN BILL
    # ------------------------

    bill = models.Bill(
        customer=bill_data.customer,
        customeradd1=bill_data.customeradd1,
        customeradd2=bill_data.customeradd2,
        total=0,
        date=bill_data.date,
        tenant_id=tenant_id
    )

    db.add(bill)
    db.commit()
    db.refresh(bill)

    # Allocate a sequential invoice_number for this tenant
    # Using SELECT FOR UPDATE to prevent race conditions
    max_invoice = db.query(func.max(models.Bill.invoice_number)).filter(
        models.Bill.tenant_id == tenant_id
    ).with_for_update().scalar() or 0
    bill.invoice_number = max_invoice + 1
    db.commit()

    # ------------------------
    # SAVE BILL ITEMS
    # ------------------------

    for item in bill_data.items:
        item_total = round(item.qty * item.price, 2)
        total += round(item_total, 2)
        db_item = models.BillItem(
            bill_id=bill.id,
            description=item.description,
            note=item.note,
            qty=item.qty,
            unit=item.unit,
            price=item.price,
            total=item_total
        )
        db.add(db_item)

    # ------------------------
    # UPDATE BILL TOTAL
    # ------------------------

    bill.total = round(total, 2)
    db.commit()

    # ====================================================
    # SAVE CUSTOMER INTO SMART MEMORY TABLE
    # ====================================================

    existing_customer = db.execute(
        text("""
            SELECT * FROM customers
            WHERE customer_name = :name AND tenant_id = :tenant_id
        """),

        {
            "name": bill_data.customer,
            "tenant_id": tenant_id
        }
    ).fetchone()

    # IF CUSTOMER DOES NOT EXIST
    if not existing_customer:
        db.execute(
            text("""
                INSERT INTO customers
                (
                    customer_name,
                    address1,
                    address2,
                    tenant_id
                )

                VALUES
                (
                    :name,
                    :add1,
                    :add2,
                    :tenant_id
                )
            """),

            {
                "name": bill_data.customer,
                "add1": bill_data.customeradd1,
                "add2": bill_data.customeradd2,
                "tenant_id": tenant_id
            }
        )
        db.commit()

    # ====================================================
    # SAVE ITEMS INTO SMART MEMORY TABLE
    # ====================================================

    for item in bill_data.items:
        existing_item = db.execute(
            text("""
                SELECT * FROM items
                WHERE description = :desc AND tenant_id = :tenant_id
            """),
            {
                "desc": item.description,
                "tenant_id": tenant_id
            }
        ).fetchone()

        # IF ITEM DOES NOT EXIST
        if not existing_item:
            db.execute(
                text("""
                    INSERT INTO items
                    (
                        description,
                        unit,
                        price,
                        tenant_id
                    )
                    VALUES
                    (
                        :desc,
                        :unit,
                        :price,
                        :tenant_id
                    )
                """),
                {
                    "desc": item.description,
                    "unit": item.unit,
                    "price": item.price,
                    "tenant_id": tenant_id
                }
            )
    db.commit()
    return bill