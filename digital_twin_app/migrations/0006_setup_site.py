"""
Custom migration to set up the Site model for django-allauth
"""
from django.db import migrations


def update_site_name(apps, schema_editor):
    """Update the site name and domain"""
    Site = apps.get_model('sites', 'Site')
    
    # Get the first site object or create if it doesn't exist
    site_obj = Site.objects.filter(id=1).first()
    if not site_obj:
        site_obj = Site(id=1)
    
    site_obj.domain = 'localhost:8000'
    site_obj.name = 'Digital Twin'
    site_obj.save()


def reverse_site_name(apps, schema_editor):
    """Revert the site name and domain"""
    Site = apps.get_model('sites', 'Site')
    site_obj = Site.objects.filter(id=1).first()
    if site_obj:
        site_obj.domain = 'example.com'
        site_obj.name = 'example.com'
        site_obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
        ('digital_twin_app', '0005_userprofile'),
    ]

    operations = [
        migrations.RunPython(update_site_name, reverse_site_name),
    ]
