from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import Cart, Coupon, Invoice, InvoiceItem, Order, OrderItem


def get_cart(request):
    if not request.user.is_authenticated:
        raise PermissionDenied("Authentication credentials were not provided.")
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return cart


def merge_session_cart(request, user):
    return None


def build_order_amounts(cart, items):
    subtotal = sum((item.line_total for item in items), Decimal("0.00"))
    discount = Decimal("0.00")
    if cart.coupon and cart.subtotal:
        discount = min(subtotal, cart.discount * (subtotal / cart.subtotal))
    shipping = Decimal("0.00") if subtotal >= Decimal("2500.00") or subtotal == 0 else Decimal("149.00")
    total = max(Decimal("0.00"), subtotal - discount + shipping)
    return subtotal, discount, shipping, total


def quantize_money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_address(order):
    return ", ".join(
        part for part in [
            order.full_name,
            order.address_line1,
            order.address_line2,
            order.city,
            order.state,
            order.postal_code,
        ] if part
    )


def next_invoice_number():
    latest = Invoice.objects.order_by("-id").values_list("id", flat=True).first() or 0
    return f"INV-{latest + 1:06d}"


def split_tax(taxable_amount, gst_rate, intra_state):
    taxable_amount = quantize_money(taxable_amount)
    gst_rate = quantize_money(gst_rate)
    if gst_rate <= 0:
        zero = Decimal("0.00")
        return zero, zero, zero
    gst_total = quantize_money(taxable_amount * gst_rate / Decimal("100"))
    if intra_state:
        half = quantize_money(gst_total / Decimal("2"))
        return half, half, Decimal("0.00")
    return Decimal("0.00"), Decimal("0.00"), gst_total


@transaction.atomic
def ensure_invoice(order):
    if getattr(order, "invoice", None):
        return order.invoice

    seller_state = settings.SELLER_STATE.strip() or "Delhi"
    place_of_supply = order.state or seller_state
    intra_state = place_of_supply.strip().lower() == seller_state.strip().lower()
    transaction_type = "Intra-State" if intra_state else "Inter-State"
    billing_address = format_address(order)
    shipping_address = format_address(order)
    gross_amount = quantize_money(order.subtotal + order.discount)
    discount_amount = quantize_money(order.discount)
    other_charges = quantize_money(order.shipping)
    taxable_amount = quantize_money(order.subtotal - order.discount)

    invoice = Invoice.objects.create(
        order=order,
        invoice_number=next_invoice_number(),
        packet_id=f"PKT-{order.id:06d}",
        order_date=order.created_at.date(),
        transaction_type=transaction_type,
        supply_type="Goods",
        place_of_supply=place_of_supply,
        customer_name=order.full_name,
        billing_address=billing_address,
        shipping_address=shipping_address,
        customer_type="Unregistered",
        seller_name=settings.SELLER_NAME,
        seller_address=settings.SELLER_ADDRESS,
        seller_gstin=settings.SELLER_GSTIN,
        gross_amount=gross_amount,
        discount_amount=discount_amount,
        other_charges=other_charges,
        taxable_amount=taxable_amount,
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("0.00"),
        total_amount=quantize_money(order.total),
    )

    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    total_igst = Decimal("0.00")
    line_discount_remaining = discount_amount
    order_items = order.items.select_related("product").all()
    item_count = order_items.count() or 1

    for index, item in enumerate(order_items, start=1):
        proportional_discount = quantize_money((discount_amount * item.line_total / order.subtotal) if order.subtotal else Decimal("0.00"))
        if index == item_count:
            proportional_discount = line_discount_remaining
        line_discount_remaining = quantize_money(line_discount_remaining - proportional_discount)
        gross_line_amount = quantize_money(item.line_total + proportional_discount)
        taxable_line_amount = quantize_money(gross_line_amount - proportional_discount)
        gst_rate = Decimal(str(getattr(item.product, "gst_rate", 0) or 0))
        cgst_amount, sgst_amount, igst_amount = split_tax(taxable_line_amount, gst_rate, intra_state)
        total_cgst += cgst_amount
        total_sgst += sgst_amount
        total_igst += igst_amount
        InvoiceItem.objects.create(
            invoice=invoice,
            product_name=item.product_name,
            sku=getattr(item.product, "sku", "") or "",
            hsn_code=getattr(item.product, "hsn_code", "") or "",
            gst_rate=gst_rate,
            quantity=item.quantity,
            gross_amount=gross_line_amount,
            discount_amount=proportional_discount,
            taxable_amount=taxable_line_amount,
            cgst_amount=cgst_amount,
            sgst_amount=sgst_amount,
            igst_amount=igst_amount,
            total_amount=quantize_money(taxable_line_amount + cgst_amount + sgst_amount + igst_amount),
        )

    invoice.cgst_amount = quantize_money(total_cgst)
    invoice.sgst_amount = quantize_money(total_sgst)
    invoice.igst_amount = quantize_money(total_igst)
    invoice.save(update_fields=["cgst_amount", "sgst_amount", "igst_amount"])
    return invoice


def build_invoice_pdf(invoice, request=None):
    try:
        import qrcode
        from reportlab.graphics.barcode import code128
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader, simpleSplit
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("reportlab and qrcode are required for invoice PDF generation") from exc

    order = invoice.order
    items = list(invoice.items.all())
    page_width, page_height = A4
    margin = 12 * mm
    content_width = page_width - (margin * 2)
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    pdf.setTitle(invoice.invoice_number)

    def draw_text(x, y, text, size=9, bold=False):
      pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
      pdf.drawString(x, y, str(text or ""))

    def draw_right_text(x, y, text, size=9, bold=False):
      pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
      pdf.drawRightString(x, y, str(text or ""))

    def draw_box(x, y_top, width, height):
      pdf.rect(x, y_top - height, width, height, stroke=1, fill=0)

    def draw_cell_text(x, y_top, width, height, text, size=8, bold=False, right=False):
      lines = simpleSplit(str(text or ""), "Helvetica-Bold" if bold else "Helvetica", size, max(width - 6, 20))
      for index, line in enumerate(lines[:3]):
        line_y = y_top - 11 - (index * (size + 2))
        if right:
          draw_right_text(x + width - 3, line_y, line, size=size, bold=bold)
        else:
          draw_text(x + 3, line_y, line, size=size, bold=bold)

    y = page_height - margin
    draw_text(margin, y, "Tax Invoice", size=18, bold=True)

    barcode = code128.Code128(invoice.invoice_number, barHeight=13 * mm, barWidth=0.42)
    barcode_x = page_width - margin - 60 * mm
    barcode_y = y - 11
    barcode.drawOn(pdf, barcode_x, barcode_y)

    y -= 20
    row_h = 16
    col_widths = [content_width * 0.23, content_width * 0.27, content_width * 0.23, content_width * 0.27]
    meta_rows = [
      ("Invoice Number:", invoice.invoice_number, "PacketID:", invoice.packet_id or "-"),
      ("Order Number:", order.id, "Invoice Date:", invoice.invoice_date.strftime("%d %b %Y")),
      ("Nature of Transaction:", invoice.transaction_type, "Order Date:", invoice.order_date.strftime("%d %b %Y")),
      ("Place of Supply:", invoice.place_of_supply, "Nature of Supply:", invoice.supply_type),
    ]
    table_x = margin
    table_y = y
    for row in meta_rows:
      x = table_x
      for index, cell in enumerate(row):
        draw_box(x, table_y, col_widths[index], row_h)
        draw_cell_text(x, table_y, col_widths[index], row_h, cell, size=8, bold=index % 2 == 0)
        x += col_widths[index]
      table_y -= row_h
    y = table_y - 6

    pdf.line(margin, y, page_width - margin, y)
    y -= 6
    address_heights = 68
    address_widths = [content_width * 0.34, content_width * 0.33, content_width * 0.33]
    address_blocks = [
      ("Bill to / Ship to:", [invoice.customer_name, invoice.shipping_address, f"Customer Type: {invoice.customer_type}"]),
      ("Bill From:", [invoice.seller_name, invoice.seller_address]),
      ("Ship From:", [invoice.seller_name, settings.SELLER_WAREHOUSE_ADDRESS, f"GSTIN Number: {invoice.seller_gstin or '-'}"]),
    ]
    x = margin
    for index, block in enumerate(address_blocks):
      draw_box(x, y, address_widths[index], address_heights)
      draw_cell_text(x, y, address_widths[index], address_heights, block[0], size=8, bold=True)
      text_y = y - 18
      for line in block[1]:
        for wrapped_index, wrapped in enumerate(simpleSplit(str(line or ""), "Helvetica", 8, address_widths[index] - 6)[:4]):
          draw_text(x + 3, text_y, wrapped, size=8)
          text_y -= 10
      x += address_widths[index]
    y -= address_heights + 6

    pdf.line(margin, y, page_width - margin, y)
    y -= 6
    item_col_widths = [content_width * 0.05, content_width * 0.22, content_width * 0.11, content_width * 0.08, content_width * 0.08, content_width * 0.11, content_width * 0.08, content_width * 0.08, content_width * 0.08, content_width * 0.05, content_width * 0.14]
    item_headers = ["Qty", "Product Details", "Gross Amount", "Discount", "Other Charges", "Taxable Amount", "CGST", "SGST/UGST", "IGST", "Cess", "Total Amount"]
    table_y = y
    x = margin
    header_h = 18
    for index, header in enumerate(item_headers):
      draw_box(x, table_y, item_col_widths[index], header_h)
      draw_cell_text(x, table_y, item_col_widths[index], header_h, header, size=7, bold=True, right=index not in {1})
      x += item_col_widths[index]
    table_y -= header_h

    other_charges_remaining = quantize_money(invoice.other_charges)
    for idx, item in enumerate(items, start=1):
      allocated_other = Decimal("0.00")
      if invoice.other_charges:
        if idx == len(items):
          allocated_other = other_charges_remaining
        else:
          allocated_other = quantize_money(invoice.other_charges * item.taxable_amount / invoice.taxable_amount) if invoice.taxable_amount else Decimal("0.00")
          other_charges_remaining = quantize_money(other_charges_remaining - allocated_other)
      row_values = [
        item.quantity,
        f"{item.sku or '-'} - {item.product_name}{', ' + item.order_item.variant_name if getattr(item, 'order_item', None) and item.order_item.variant_name else ''}\nHSN: {item.hsn_code or '-'} | GST Rate: {item.gst_rate}%",
        f"Rs. {item.gross_amount}",
        f"Rs. {item.discount_amount}",
        f"Rs. {allocated_other}",
        f"Rs. {item.taxable_amount}",
        f"Rs. {item.cgst_amount}",
        f"Rs. {item.sgst_amount}",
        f"Rs. {item.igst_amount}",
        "Rs. 0.00",
        f"Rs. {item.total_amount}",
      ]
      row_h = 32
      x = margin
      for col_index, value in enumerate(row_values):
        draw_box(x, table_y, item_col_widths[col_index], row_h)
        draw_cell_text(x, table_y, item_col_widths[col_index], row_h, value, size=7, bold=False, right=col_index not in {1})
        x += item_col_widths[col_index]
      table_y -= row_h

    total_values = ["", "TOTAL", f"Rs. {invoice.gross_amount}", f"Rs. {invoice.discount_amount}", f"Rs. {invoice.other_charges}", f"Rs. {invoice.taxable_amount}", f"Rs. {invoice.cgst_amount}", f"Rs. {invoice.sgst_amount}", f"Rs. {invoice.igst_amount}", f"Rs. {invoice.cess_amount}", f"Rs. {invoice.total_amount}"]
    x = margin
    total_h = 18
    for col_index, value in enumerate(total_values):
      draw_box(x, table_y, item_col_widths[col_index], total_h)
      draw_cell_text(x, table_y, item_col_widths[col_index], total_h, value, size=7, bold=True, right=col_index not in {1})
      x += item_col_widths[col_index]
    y = table_y - total_h - 8

    signature_w = content_width * 0.58
    qr_w = content_width * 0.42
    footer_h = 82
    draw_box(margin, y, signature_w, footer_h)
    draw_box(margin + signature_w, y, qr_w, footer_h)
    draw_text(margin + 4, y - 12, invoice.seller_name, size=9)
    draw_text(margin + 4, y - 54, "Authorized Signatory", size=9, bold=True)

    qr_payload = "\n".join([
      f"Invoice: {invoice.invoice_number}",
      f"Order: {invoice.order_id}",
      f"Amount: Rs. {invoice.total_amount}",
      f"Payment: {order.selected_payment_method or order.payment_method}",
      f"Customer: {invoice.customer_name}",
      f"Date: {invoice.invoice_date:%d-%m-%Y}",
    ])
    qr = qrcode.QRCode(version=2, box_size=3, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    pdf.drawImage(ImageReader(BytesIO(qr_buffer.getvalue())), margin + signature_w + qr_w - 26 * mm, y - 64, width=22 * mm, height=22 * mm)
    draw_right_text(page_width - margin - 4, y - 70, "Scan for invoice details", size=7)
    y -= footer_h + 8

    draw_text(margin, y, "DECLARATION", size=9, bold=True)
    y -= 11
    for line in simpleSplit("The goods sold as part of this shipment are intended for end-user consumption and are not for retail sale", "Helvetica", 8, content_width):
      draw_text(margin, y, line, size=8)
      y -= 9
    y -= 3
    draw_text(margin, y, f"Registered Address: {settings.SELLER_REGISTERED_ADDRESS}", size=8)
    y -= 10
    draw_text(margin, y, settings.INVOICE_HELP_TEXT, size=8)
    draw_right_text(page_width - margin, y, settings.BRAND_LOGO_TEXT, size=12, bold=True)

    pdf.showPage()
    pdf.save()
    pdf_bytes = output.getvalue()
    filename = f"{invoice.invoice_number}.pdf"
    invoice.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    return pdf_bytes


@transaction.atomic
def place_order(user, cart, data, items_queryset=None, *, payment_status=Order.PAYMENT_PENDING, selected_payment_method=""):
    items_queryset = items_queryset or cart.items.select_related("product", "variant")
    items = list(items_queryset)
    subtotal, discount, shipping, total = build_order_amounts(cart, items)
    order = Order.objects.create(
        user=user,
        coupon=cart.coupon,
        full_name=data["full_name"],
        email=data["email"],
        phone=data["phone"],
        address_line1=data["address_line1"],
        address_line2=data.get("address_line2", ""),
        city=data["city"],
        state=data["state"],
        postal_code=data["postal_code"],
        payment_method=data.get("payment_method", "cod"),
        payment_status=payment_status,
        selected_payment_method=selected_payment_method or data.get("selected_payment_method", ""),
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        total=total,
    )
    for item in items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            variant_name=f"{item.variant.name}: {item.variant.value}" if item.variant else "",
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        item.product.stock = max(0, item.product.stock - item.quantity)
        item.product.save(update_fields=["stock"])
    if cart.coupon:
        Coupon.objects.filter(id=cart.coupon_id).update(used_count=cart.coupon.used_count + 1)
    cart.items.filter(id__in=[item.id for item in items]).delete()
    cart.coupon = None
    cart.save(update_fields=["coupon"])
    ensure_invoice(order)
    return order
