from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0003_invoice_invoiceitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="razorpay_order_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="order",
            name="razorpay_payment_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="order",
            name="razorpay_signature",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
