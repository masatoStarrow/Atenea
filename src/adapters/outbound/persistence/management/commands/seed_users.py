"""
Management command: seed_users

Creates initial users via dual-write:
  1. Saves to Gateway DB (with password hash)
  2. POSTs to Artemisa (users-service) with the SAME UUID, no password

This guarantees both services share identical UUIDs for all seed users.
Requires Artemisa to be running before this command is executed.
"""

from django.core.management.base import BaseCommand

from src.adapters.outbound.persistence.django_user_repository import DjangoUserRepository
from src.adapters.outbound.http_client.users_client import UsersServiceClient
from src.application.use_cases.create_user_gateway import CreateUserGateway
from src.domain.exceptions import EmailAlreadyExistsError, ServiceUnavailableError

# Bootstrap UUID used as requester identity during seeding (no real user exists yet)
BOOTSTRAP_USER_ID = '00000000-0000-0000-0000-000000000000'


class Command(BaseCommand):
    help = (
        'Seeds both Gateway DB and Artemisa (users-service) with initial users '
        'using the dual-write flow. All users share the same UUID across both services.'
    )

    SEED_USERS = [
        {
            'email': 'admin@crm.com',
            'full_name': 'Administrador CRM',
            'role': 'admin',
            'password': 'Temporal123!',
        },
        {
            'email': 'soporte@crm.com',
            'full_name': 'Agente Soporte',
            'role': 'soporte',
            'password': 'Temporal123!',
        },
        {
            'email': 'comercial@crm.com',
            'full_name': 'Agente Comercial',
            'role': 'comercial',
            'password': 'Temporal123!',
        },
    ]

    def handle(self, *args, **options):
        repo = DjangoUserRepository()
        client = UsersServiceClient()
        use_case = CreateUserGateway(
            user_repository=repo,
            users_client=client,
        )

        created = 0
        skipped = 0
        failed = 0

        for user_data in self.SEED_USERS:
            email = user_data['email']
            try:
                use_case.execute(
                    email=email,
                    full_name=user_data['full_name'],
                    role=user_data['role'],
                    password=user_data['password'],
                    request_user_id=BOOTSTRAP_USER_ID,
                    request_user_role='admin',
                )
                self.stdout.write(
                    self.style.SUCCESS(f'[dual-write] Created: {email} ({user_data["role"]})')
                )
                created += 1

            except EmailAlreadyExistsError:
                self.stdout.write(
                    self.style.WARNING(f'[skip] {email} already exists in Gateway DB')
                )
                skipped += 1

            except ServiceUnavailableError as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f'[error] {email} — Artemisa unavailable: {exc}. '
                        'Make sure the users-service is running before seeding.'
                    )
                )
                failed += 1

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Seed completed — created: {created}, skipped: {skipped}, failed: {failed}'
            )
        )
