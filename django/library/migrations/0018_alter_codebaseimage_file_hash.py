# Generated by Django 3.2.15 on 2022-08-30 18:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0017_alter_codebasereleasedownload_reason'),
    ]

    operations = [
        migrations.AlterField(
            model_name='codebaseimage',
            name='file_hash',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=40),
        ),
    ]
