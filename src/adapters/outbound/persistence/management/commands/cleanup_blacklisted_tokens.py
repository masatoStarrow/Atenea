"""
Django management command to clean expired blacklisted tokens.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from src.adapters.outbound.persistence.models.blacklisted_token_model import BlacklistedToken


class Command(BaseCommand):
    """Clean expired blacklisted JWT tokens from database."""
    
    help = 'Remove expired blacklisted tokens from database'

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many tokens would be deleted without actually deleting them',
        )
        parser.add_argument(
            '--older-than-hours',
            type=int,
            default=0,
            help='Delete tokens expired more than X hours ago (default: 0 = all expired)',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        now = timezone.now()
        
        # Calculate cutoff date
        if options['older_than_hours'] > 0:
            from datetime import timedelta
            cutoff = now - timedelta(hours=options['older_than_hours'])
            query = BlacklistedToken.objects.filter(expires_at__lt=cutoff)
        else:
            query = BlacklistedToken.objects.filter(expires_at__lt=now)
        
        count = query.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No expired tokens found to clean up')
            )
            return
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would delete {count} expired tokens'
                )
            )
        else:
            deleted_count, _ = query.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted_count} expired tokens'
                )
            )