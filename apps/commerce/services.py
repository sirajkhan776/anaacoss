import base64
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.template.loader import render_to_string

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
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise RuntimeError("xhtml2pdf is required for invoice PDF generation") from exc

    context = build_invoice_context(invoice, request=request)
    html = render_to_string("commerce/invoice_pdf.html", context)
    output = BytesIO()
    result = pisa.CreatePDF(src=html, dest=output, encoding="utf-8")
    if result.err:
        raise RuntimeError("Invoice PDF generation failed")
    pdf_bytes = output.getvalue()
    filename = f"{invoice.invoice_number}.pdf"
    invoice.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    return pdf_bytes


def image_bytes_to_data_uri(payload, mime_type="image/png"):
    return f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}"


def build_invoice_barcode_data(invoice_number):
    try:
        from barcode import Code128
        from barcode.writer import ImageWriter
    except ImportError as exc:
        raise RuntimeError("python-barcode is required for invoice barcode generation") from exc

    buffer = BytesIO()
    barcode = Code128(invoice_number, writer=ImageWriter())
    barcode.write(
        buffer,
        options={
            "module_width": 0.23,
            "module_height": 11,
            "quiet_zone": 1.2,
            "font_size": 8,
            "text_distance": 1,
            "dpi": 200,
        },
    )
    return image_bytes_to_data_uri(buffer.getvalue())


def build_invoice_qr_data(invoice):
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("qrcode is required for invoice QR generation") from exc

    qr_payload = "\n".join(
        [
            f"Invoice: {invoice.invoice_number}",
            f"Order: {invoice.order_id}",
            f"Amount: Rs. {invoice.total_amount}",
            f"Payment: {invoice.order.selected_payment_method or invoice.order.payment_method}",
            f"Customer: {invoice.customer_name}",
            f"Date: {invoice.invoice_date:%d-%m-%Y}",
        ]
    )
    qr = qrcode.QRCode(version=2, box_size=4, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return image_bytes_to_data_uri(buffer.getvalue())


def build_invoice_context(invoice, request=None):
    order = invoice.order
    items = list(invoice.items.all())
    other_charges_remaining = quantize_money(invoice.other_charges)
    item_rows = []
    for index, item in enumerate(items, start=1):
        allocated_other = Decimal("0.00")
        if invoice.other_charges:
            if index == len(items):
                allocated_other = other_charges_remaining
            else:
                allocated_other = quantize_money(invoice.other_charges * item.taxable_amount / invoice.taxable_amount) if invoice.taxable_amount else Decimal("0.00")
                other_charges_remaining = quantize_money(other_charges_remaining - allocated_other)
        item_rows.append(
            {
                "item": item,
                "allocated_other_charges": quantize_money(allocated_other),
                "display_name": f"{item.sku or '-'} - {item.product_name}",
                "hsn_display": item.hsn_code or "-",
                "gst_display": f"{item.gst_rate}%",
            }
        )

    return {
        "invoice": invoice,
        "order": order,
        "items": items,
        "invoice_item_rows": item_rows,
        "request": request,
        "barcode_data_uri": build_invoice_barcode_data(invoice.invoice_number),
        "qr_data_uri": build_invoice_qr_data(invoice),
        "seller_warehouse_address": settings.SELLER_WAREHOUSE_ADDRESS,
        "seller_registered_address": settings.SELLER_REGISTERED_ADDRESS,
        "seller_signature_name": settings.SELLER_SIGNATURE_NAME,
        "invoice_help_text": settings.INVOICE_HELP_TEXT,
        "brand_logo_text": settings.BRAND_LOGO_TEXT,
    }


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
