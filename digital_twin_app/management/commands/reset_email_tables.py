"""
Django management command to drop email tables and migrate fresh
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Drop existing email tables and apply fresh migrations'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Disable foreign key constraints temporarily
            cursor.execute("PRAGMA foreign_keys = OFF;")
            
            # Check what email tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND (name LIKE '%email%' OR name LIKE '%validated%');
            """)
            tables = cursor.fetchall()
            
            self.stdout.write(f"Found email-related tables: {[table[0] for table in tables]}")
            
            # Drop existing email tables if they exist (in correct order to handle dependencies)
            email_tables = [
                'digital_twin_app_emailmessage',  # Drop this first (has FK to emailaccount)
                'digital_twin_app_emailaccount',  # Drop this second (has FK to user)
                'digital_twin_app_validatedsender'  # Drop this last (no dependencies)
            ]
            
            for table in email_tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table};")
                    self.stdout.write(f"Dropped table: {table}")
                except Exception as e:
                    self.stdout.write(f"Could not drop {table}: {e}")
            
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # Remove the migration record
            try:
                cursor.execute("""
                    DELETE FROM django_migrations 
                    WHERE app = 'digital_twin_app' AND name = '0003_email_integration';
                """)
                self.stdout.write("Removed migration record for 0003_email_integration")
            except Exception as e:
                self.stdout.write(f"Could not remove migration record: {e}")
        
        # Apply the migration fresh
        self.stdout.write("Applying fresh migrations...")
        call_command('migrate', verbosity=1)
        
        self.stdout.write(self.style.SUCCESS("Successfully dropped email tables and applied fresh migrations!"))
