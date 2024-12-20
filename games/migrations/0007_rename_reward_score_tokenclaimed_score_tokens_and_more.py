# Generated by Django 5.1.3 on 2024-12-11 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0006_alter_score_game'),
    ]

    operations = [
        migrations.RenameField(
            model_name='score',
            old_name='reward',
            new_name='tokenClaimed',
        ),
        migrations.AddField(
            model_name='score',
            name='tokens',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='score',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
