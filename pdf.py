from supabase import create_client
import uuid
from weasyprint import HTML
from dotenv import load_dotenv
load_dotenv()
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_pdf(filename, bill, items):

    # 🔹 Generate table rows
    rows = ""

    for i, item in enumerate(items, start=1):

        unit_display = item.unit.strip()

        price_unit = (
            unit_display
            if unit_display.lower().startswith("per")
            else f"per {unit_display}"
        )

        rows += f"""
        <tr>
            <td>{i}</td>

            <td class="col-desc">
                <b>{item.description}</b><br>
                <span style="font-size:11px; display:block; margin-top:3px">
                    {item.note or ""}
                </span>
            </td>

            <td>
                {format(item.qty, ".2f").rstrip('0').rstrip('.')}<br>
                <span style="font-size:11px; display:block; margin-top:3px">
                    {unit_display}
                </span>
            </td>

            <td>
                ₹ {item.price}<br>
                <span style="font-size:11px;">
                    {price_unit}
                </span>
            </td>

            <td>
                ₹ {format(item.total, ".2f")}
            </td>

        </tr>
        """

    # 🔥 Safe total calculation
    calculated_total = sum(item.total for item in items)

    # 🔹 HTML TEMPLATE
    html = f"""
    <!DOCTYPE html>

    <html>

    <head>

    <meta charset="UTF-8">

    <style>
    @page {{
        size: A4;
        margin: 8mm;
    }}
    body {{
        font-family: Arial, sans-serif;
        padding: 15px;
        line-height: 1.3;
        color: #111;
    }}

    .container {{
        border: 2px solid black;
        padding: 18px;
        width: 92%;
        max-width: 760px;
        margin: auto;
        box-sizing: border-box;
    }}

    .title {{
        text-align: center;
        font-weight: bold;
        font-size: 24px;
        letter-spacing: 1px;
        margin-bottom: 20px;
        color: #111;
    }}

    .customer-section {{
        margin-bottom: 25px;
        font-size: 15px;
    }}

    p {{
        margin-top: 10px;
        margin-bottom: 20px;
        font-size: 15px;
    }}

    .header {{
        width: 100%;
        margin-bottom: 25px;
    }}

    .left {{
        float: left;
        font-size: 14px;
    }}

    .right {{
        float: right;
        text-align: right;
        font-size: 14px;
    }}

    .clearfix {{
        clear: both;
    }}

    table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 15px;
        box-sizing: border-box;
        page-break-inside: avoid;
    }}

    th {{
        background-color: #dcdcdc;
        font-weight: bold;
        text-transform: uppercase;
        font-size: 15px;
    }}

    /*th, td {{
        border: 1px solid black;
        padding: 14px 10px;
        font-size: 14px;
        line-height: 1.4;
        overflow-wrap: break-word;
        vertical-align: top;
        word-break: break-word;
    }}*/
    th, td {{
        border: 1px solid black;
        padding: 10px 8px;
        font-size: 13px;
        line-height: 1.3;
        vertical-align: top;
    }}

    td {{
        text-align: center;
        word-wrap: break-word;
    }}

    .col-desc {{
        text-align: left;
    }}

    .total-row {{
        font-weight: bold;
    }}

    .grand-total {{
        font-weight: bold;
        background-color: #f2f2f2;
    }}

    .footer {{
        margin-top: 30px;
    }}

    .signature {{
        text-align: right;
        margin-top: 45px;
        font-size: 15px;
    }}

    .col-sno {{
        width: 6%;
    }}

    .col-desc {{
        width: 44%;
    }}

    .col-qty {{
        width: 16%;
    }}

    .col-price {{
        width: 17%;
    }}

    .col-total {{
        width: 17%;
    }}

    </style>

    </head>

    <body>

    <div class="container">

        <div class="title">BILL</div>

        <div class="header">

            <div class="left">
                <b>Devendra Singh Shekhawat</b><br>
                Gandhi Path West<br>
                302021<br>
                8290007899
            </div>

            <div class="right">
                <b>Bill No:</b> {bill.id}<br>
                <b>Date:</b> {bill.date.strftime("%d/%m/%Y")}
            </div>

            <div class="clearfix"></div>

        </div>

        <br>

        <div class="customer-section">
            <b>To,</b><br>

            {bill.customer}<br>

            {f"{bill.customeradd1}<br>" if bill.customeradd1 else ""}

            {bill.customeradd2 if bill.customeradd2 else ""}
        </div>

        <br>

        <p>
            Dear Sir/Mam<br>
            Thank you for your valuable inquiry.
            We are pleased to quote as below.
        </p>

        <table>

            <tr>
                <th class="col-sno">#</th>
                <th class="col-desc">Description</th>
                <th class="col-qty">Qty</th>
                <th class="col-price">Price</th>
                <th class="col-total">Total</th>
            </tr>

            {rows}

            <tr class="total-row">
                <td colspan="4" style="text-align:right;">
                    TOTAL
                </td>

                <td style="text-align:right; white-space:nowrap; padding-right:10px;">
                    ₹ {format(calculated_total, ".2f")}
                </td>
            </tr>

            <tr class="grand-total">
                <td colspan="4" style="text-align:right; white-space:nowrap;">
                    GRAND TOTAL
                </td>

                <td>
                    <b>₹ {format(calculated_total, ".2f")}</b>
                </td>
            </tr>

        </table>

        <div class="footer">

            <div>
                <b>Account Details for Payments</b><br>

                State Bank Of India<br>
                A/c Holder Name - Devendra Shekhawat<br>
                A/c No - 39860765723<br>
                IFSC CODE - SBIN0061316
            </div>

            <div class="signature">
                Authorized Signature
            </div>

        </div>

    </div>

    </body>

    </html>
    """

    # 🔥 NEW PDF GENERATION USING WEASYPRINT
    HTML(string=html).write_pdf(filename)

    print("PDF GENERATED:", filename)

    return filename