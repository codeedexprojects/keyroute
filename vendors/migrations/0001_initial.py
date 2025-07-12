import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('admin_panel', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('time', models.TimeField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Amenity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('icon', models.ImageField(blank=True, null=True, upload_to='amenity/icons/', validators=[django.core.validators.FileExtensionValidator(['jpg', 'jpeg', 'png', 'svg'])])),
            ],
        ),
        migrations.CreateModel(
            name='BusFeature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='DayPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_number', models.PositiveIntegerField()),
                ('description', models.TextField(blank=True, null=True)),
                ('night', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='PackageCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='package_categories/')),
            ],
        ),
        migrations.CreateModel(
            name='SignupOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.CharField(max_length=100)),
                ('otp_code', models.CharField(max_length=6)),
                ('signup_data', models.JSONField()),
                ('otp_type', models.CharField(choices=[('mobile', 'Mobile'), ('email', 'Email')], max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('role', models.CharField(choices=[('admin', 'Admin'), ('vendor', 'Vendor'), ('user', 'User')], default='vendor', max_length=30)),
            ],
            options={
                'db_table': 'signup_otp',
            },
        ),
        migrations.CreateModel(
            name='ActivityImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='packages/activities/')),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='vendors.activity')),
            ],
        ),
        migrations.CreateModel(
            name='Bus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bus_name', models.CharField(blank=True, max_length=255, null=True)),
                ('bus_number', models.CharField(blank=True, max_length=20, null=True, unique=True)),
                ('capacity', models.IntegerField(blank=True, null=True)),
                ('vehicle_description', models.TextField(blank=True, null=True)),
                ('travels_logo', models.ImageField(blank=True, null=True, upload_to='travels_logos/')),
                ('rc_certificate', models.FileField(blank=True, null=True, upload_to='rc_certificates/')),
                ('license', models.FileField(blank=True, null=True, upload_to='licenses/')),
                ('contract_carriage_permit', models.FileField(blank=True, null=True, upload_to='permits/')),
                ('passenger_insurance', models.FileField(blank=True, null=True, upload_to='insurance/')),
                ('vehicle_insurance', models.FileField(blank=True, null=True, upload_to='insurance/')),
                ('base_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('base_price_km', models.DecimalField(blank=True, decimal_places=2, default=100.0, help_text='KM included per day in base price', max_digits=10, null=True)),
                ('price_per_km', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('night_allowance', models.DecimalField(blank=True, decimal_places=2, default=0.0, help_text='Additional charge per night', max_digits=10, null=True)),
                ('minimum_fare', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('status', models.CharField(blank=True, choices=[('available', 'Available'), ('booked', 'Booked'), ('maintenance', 'Under Maintenance')], default='available', max_length=20, null=True)),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
                ('latitude', models.FloatField(blank=True, null=True)),
                ('longitude', models.FloatField(blank=True, null=True)),
                ('bus_type', models.CharField(blank=True, max_length=50, null=True)),
                ('is_popular', models.BooleanField(default=False)),
                ('amenities', models.ManyToManyField(blank=True, related_name='buses', to='vendors.amenity')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='admin_panel.vendor')),
                ('features', models.ManyToManyField(blank=True, related_name='buses', to='vendors.busfeature')),
            ],
        ),
        migrations.CreateModel(
            name='BusImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bus_view_image', models.ImageField(blank=True, null=True, upload_to='bus_views/')),
                ('bus', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='vendors.bus')),
            ],
        ),
        migrations.CreateModel(
            name='BusTravelImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='bus_travel_images/')),
                ('bus', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='travel_images', to='vendors.bus')),
            ],
        ),
        migrations.AddField(
            model_name='activity',
            name='day_plan',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='vendors.dayplan'),
        ),
        migrations.CreateModel(
            name='Meal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('dinner', 'Dinner')], max_length=50)),
                ('description', models.TextField(blank=True, null=True)),
                ('restaurant_name', models.CharField(blank=True, max_length=255, null=True)),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
                ('time', models.TimeField(blank=True, null=True)),
                ('day_plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meals', to='vendors.dayplan')),
            ],
        ),
        migrations.CreateModel(
            name='MealImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='packages/meals/')),
                ('meal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='vendors.meal')),
            ],
        ),
        migrations.CreateModel(
            name='OTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('otp_code', models.CharField(max_length=6)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Package',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('header_image', models.ImageField(upload_to='packages/header/', validators=[django.core.validators.FileExtensionValidator(['jpg', 'png'])])),
                ('places', models.CharField(max_length=255)),
                ('days', models.PositiveIntegerField(default=0)),
                ('ac_available', models.BooleanField(default=True, verbose_name='AC Available')),
                ('guide_included', models.BooleanField(default=False, verbose_name='Includes Guide')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bus_location', models.CharField(blank=True, max_length=255, null=True)),
                ('price_per_person', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('extra_charge_per_km', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('status', models.CharField(choices=[('available', 'Available'), ('booked', 'Booked'), ('expired', 'Expired')], default='available', max_length=20)),
                ('buses', models.ManyToManyField(to='vendors.bus')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='admin_panel.vendor')),
            ],
        ),
        migrations.AddField(
            model_name='dayplan',
            name='package',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='day_plans', to='vendors.package'),
        ),
        migrations.CreateModel(
            name='PackageImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='packages/images/', validators=[django.core.validators.FileExtensionValidator(['jpg', 'jpeg', 'png'])])),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='package_images', to='vendors.package')),
            ],
        ),
        migrations.CreateModel(
            name='PackageSubCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='package_subcategories/')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subcategories', to='vendors.packagecategory')),
            ],
        ),
        migrations.AddField(
            model_name='package',
            name='sub_category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='packages', to='vendors.packagesubcategory'),
        ),
        migrations.CreateModel(
            name='Place',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('day_plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='places', to='vendors.dayplan')),
            ],
        ),
        migrations.CreateModel(
            name='PlaceImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='packages/places/')),
                ('place', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='vendors.place')),
            ],
        ),
        migrations.CreateModel(
            name='Stay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hotel_name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
                ('is_ac', models.BooleanField(blank=True, default=False, null=True)),
                ('has_breakfast', models.BooleanField(blank=True, default=False, null=True)),
                ('day_plan', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stay', to='vendors.dayplan')),
            ],
        ),
        migrations.CreateModel(
            name='StayImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='packages/stays/')),
                ('stay', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='vendors.stay')),
            ],
        ),
        migrations.CreateModel(
            name='VendorBankDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('holder_name', models.CharField(blank=True, max_length=100, null=True)),
                ('payout_mode', models.CharField(blank=True, max_length=50, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=15, null=True)),
                ('ifsc_code', models.CharField(blank=True, max_length=20, null=True)),
                ('email_id', models.EmailField(blank=True, max_length=254, null=True)),
                ('account_number', models.CharField(blank=True, max_length=50, null=True)),
                ('payout_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('customer_id', models.CharField(blank=True, max_length=100, null=True)),
                ('pay_id', models.CharField(blank=True, max_length=100, null=True)),
                ('payout_narration', models.TextField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('vendor', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bank_detail', to='admin_panel.vendor')),
            ],
        ),
        migrations.CreateModel(
            name='PayoutRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_amount', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('remarks', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('processed', 'Processed')], default='pending', max_length=20)),
                ('admin_remarks', models.TextField(blank=True, null=True)),
                ('transaction_id', models.CharField(blank=True, max_length=100, null=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('processed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_payouts', to=settings.AUTH_USER_MODEL)),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payout_requests', to='admin_panel.vendor')),
                ('bank_detail', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payout_requests', to='vendors.vendorbankdetail')),
            ],
            options={
                'verbose_name': 'Payout Request',
                'verbose_name_plural': 'Payout Requests',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VendorNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='admin_panel.vendor')),
            ],
        ),
        migrations.CreateModel(
            name='VendorWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('vendor', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to='admin_panel.vendor')),
            ],
            options={
                'verbose_name': 'Vendor Wallet',
                'verbose_name_plural': 'Vendor Wallets',
            },
        ),
        migrations.CreateModel(
            name='VendorWalletTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('completed', 'Completed')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('reference_id', models.CharField(blank=True, max_length=100, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('balance_after', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='vendors.vendorwallet')),
            ],
            options={
                'verbose_name': 'Vendor Wallet Transaction',
                'verbose_name_plural': 'Vendor Wallet Transactions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VendorBusyDate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('from_time', models.TimeField(blank=True, null=True)),
                ('to_time', models.TimeField(blank=True, null=True)),
                ('reason', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('buses', models.ManyToManyField(related_name='busy_dates', to='vendors.bus')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='busy_dates', to='admin_panel.vendor')),
            ],
            options={
                'ordering': ['-date'],
                'unique_together': {('vendor', 'date', 'from_time', 'to_time')},
            },
        ),
    ]
