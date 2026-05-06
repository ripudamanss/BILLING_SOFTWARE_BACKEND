from sqlalchemy.orm import Session
import models

def create_bill(db: Session, bill_data):
    total = 0

    bill = models.Bill(
                    customer=bill_data.customer,
                    customeradd1=bill_data.customeradd1,
                    customeradd2=bill_data.customeradd2,
                    total=0,
                    date=bill_data.date)
    db.add(bill)
    db.commit()
    db.refresh(bill)

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

    bill.total = round(total, 2) # type: ignore
    db.commit()

    return bill