# Generated by Django 5.1.3 on 2024-12-10 16:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_alter_user_wallet_address'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='wallet_address',
            field=models.CharField(default=None, max_length=600),
        ),
    ]
