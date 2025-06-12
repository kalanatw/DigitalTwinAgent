"""
Django management command to run email automation
"""
import asyncio
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from digital_twin_app.models import EmailAccount
from digital_twin_app.email_service import EmailService

class Command(BaseCommand):
    help = 'Run email automation service'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=300,
            help='Check interval in seconds (default: 300)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once instead of continuously'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting email automation service (interval: {interval}s, once: {run_once})'
            )
        )
        
        if run_once:
            asyncio.run(self.process_emails_once())
        else:
            asyncio.run(self.run_continuously(interval))

    async def process_emails_once(self):
        """Process emails once"""
        accounts = EmailAccount.objects.filter(auto_reply_enabled=True, is_active=True)
        
        self.stdout.write(f'Processing {accounts.count()} active email accounts...')
        
        for account in accounts:
            try:
                self.stdout.write(f'Processing account: {account.email_address}')
                service = EmailService(account)
                await service.process_new_emails()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Processed: {account.email_address}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error processing {account.email_address}: {e}')
                )

    async def run_continuously(self, interval):
        """Run email automation continuously"""
        self.stdout.write('🔄 Starting continuous email automation...')
        self.stdout.write('Press Ctrl+C to stop')
        
        try:
            while True:
                start_time = time.time()
                
                await self.process_emails_once()
                
                # Calculate sleep time
                processing_time = time.time() - start_time
                sleep_time = max(0, interval - processing_time)
                
                if sleep_time > 0:
                    self.stdout.write(f'💤 Sleeping for {sleep_time:.1f} seconds...')
                    await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS('\n🛑 Email automation stopped by user')
            )
