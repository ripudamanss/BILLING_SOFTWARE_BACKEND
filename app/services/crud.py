from sqlalchemy import text
from sqlalchemy.orm import Session
import app.models.models as models

def create_bill(db: Session, bill_data):

    total = 0

    # ------------------------
    # CREATE MAIN BILL
    # ------------------------

    bill = models.Bill(
        customer=bill_data.customer,
        customeradd1=bill_data.customeradd1,
        customeradd2=bill_data.customeradd2,
        total=0,
        date=bill_data.date
    )

    db.add(bill)
    db.commit()
    db.refresh(bill)

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
            WHERE customer_name = :name
        """),

        {
            "name": bill_data.customer
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
                    address2
                )

                VALUES
                (
                    :name,
                    :add1,
                    :add2
                )
            """),

            {
                "name": bill_data.customer,
                "add1": bill_data.customeradd1,
                "add2": bill_data.customeradd2
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
                WHERE description = :desc
            """),
            {
                "desc": item.description
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
                        price
                    )
                    VALUES
                    (
                        :desc,
                        :unit,
                        :price
                    )
                """),
                {
                    "desc": item.description,
                    "unit": item.unit,
                    "price": item.price
                }
            )
    db.commit()
    return bill