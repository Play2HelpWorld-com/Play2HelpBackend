# Generated by Django 5.1.3 on 2024-12-03 17:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0005_alter_score_game'),
    ]

    operations = [
        migrations.AlterField(
            model_name='score',
            name='game',
            field=models.CharField(max_length=100),
        ),
    ]
