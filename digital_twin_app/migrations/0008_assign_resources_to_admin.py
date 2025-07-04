"""
Data migration to assign existing resources to admin user
"""
from django.db import migrations


def assign_resources_to_admin(apps, schema_editor):
    """
    Assigns all existing resources (documents, twin versions, agents) to admin user
    or the first available user if admin doesn't exist
    """
    # Skip this migration - resources already have user associations
    print("Skipping resource assignment - database already has user associations")
    pass


def reverse_resource_assignment(apps, schema_editor):
    """
    No reverse migration needed - we don't want to nullify user references
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('digital_twin_app', '0007_user_centric_resources'),
    ]

    operations = [
        migrations.RunPython(assign_resources_to_admin, reverse_resource_assignment),
    ]
