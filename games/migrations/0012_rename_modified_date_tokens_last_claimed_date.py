# Generated by Django 5.1.3 on 2024-12-11 19:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0011_tokens_modified_date'),
    ]

    operations = [
        migrations.RenameField(
            model_name='tokens',
            old_name='modified_date',
            new_name='last_claimed_date',
        ),
    ]
