"""
Management command: seed_users
Creates initial users for each role.
"""

from django.core.management.base import BaseCommand

from src.adapters.outbound.persistence.models.user_model import User


class Command(BaseCommand):
    help = 'Seeds the database with initial users (one per role)'

    SEED_USERS = [
        {
            'email': 'admin@crm.com',
            'full_name': 'Admin User',
            'role': 'admin',
            'password': 'Temporal123!',
        },
        {
            'email': 'soporte@crm.com',
            'full_name': 'Soporte User',
            'role': 'soporte',
            'password': 'Temporal123!',
        },
        {
            'email': 'comercial@crm.com',
            'full_name': 'Comercial User',
            'role': 'comercial',
            'password': 'Temporal123!',
        },
    ]

    def handle(self, *args, **options):
        for user_data in self.SEED_USERS:
            email = user_data['email']
            if User.objects.filter(email=email).exists():
                self.stdout.write(self.style.WARNING(f'User {email} already exists — skipping'))
                continue

            User.objects.create_user(
                email=user_data['email'],
                full_name=user_data['full_name'],
                role=user_data['role'],
                password=user_data['password'],
            )
            self.stdout.write(self.style.SUCCESS(f'Created user: {email} ({user_data["role"]})'))

        self.stdout.write(self.style.SUCCESS('Seed completed!'))
