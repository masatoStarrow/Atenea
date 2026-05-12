"""
Management command: seed_clients

Creates sample clients in Artemisa (users-service) by POSTing directly
to its /api/v1/clients/ endpoint.

Unlike users, clients are NOT dual-write — they only live in Artemisa.
Requires Artemisa to be running before this command is executed.
"""

import asyncio
import json

from django.core.management.base import BaseCommand

from src.adapters.outbound.http_client.users_client import UsersServiceClient
from src.domain.exceptions import ServiceUnavailableError


def _run_async(coro):
    """Run an async coroutine from a sync Django management command."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class Command(BaseCommand):
    help = (
        'Seeds Artemisa (users-service) with sample clients. '
        'Clients only live in Artemisa — no dual-write needed.'
    )

    SEED_CLIENTS = [
        {
            'company': 'Burger House',
            'email': 'gerencia@burgerhouse.com',
            'phone': '+52-555-400-5000',
            'status': 'active',
        },
        {
            'company': 'Cafe de Origen',
            'email': 'ventas@cafedeorigen.com',
            'phone': '+52-555-700-8000',
            'status': 'active',
        },
        {
            'company': 'Didi Food MX',
            'email': 'restaurantes@didifood.com',
            'phone': '+52-555-300-4000',
            'status': 'active',
        },
        {
            'company': 'NU Bank',
            'email': 'empresas@nu.com.mx',
            'phone': '+52-555-200-3000',
            'status': 'active',
        },
        {
            'company': 'Pizza Tradizionale',
            'email': 'contacto@pizzatradizionale.com',
            'phone': '+52-555-500-6000',
            'status': 'active',
        },
        {
            'company': 'Sushi Express',
            'email': 'contacto@sushiexpress.com',
            'phone': '+52-555-100-2000',
            'status': 'active',
        },
        {
            'company': 'Tacos El Pastor',
            'email': 'info@tacoselpastor.com',
            'phone': None,
            'status': 'inactive',
        },
        {
            'company': 'Wok & Roll',
            'email': 'contacto@wokandroll.com',
            'phone': '+52-555-800-9000',
            'status': 'active',
        },
    ]

    def handle(self, *args, **options):
        http_client = UsersServiceClient()
        created = 0
        skipped = 0
        failed = 0

        for client_data in self.SEED_CLIENTS:
            email = client_data['email']
            company = client_data['company']

            # Build JSON body (filter out None values)
            payload = {k: v for k, v in client_data.items() if v is not None}
            body = json.dumps(payload).encode()

            try:
                response = _run_async(
                    http_client.forward_request(
                        method='POST',
                        path='/clients',
                        body=body,
                        query_params=None,
                        user_id='00000000-0000-0000-0000-000000000000',
                        user_role='admin',
                    )
                )

                if response.status_code == 201:
                    self.stdout.write(
                        self.style.SUCCESS(f'[created] {company} ({email})')
                    )
                    created += 1
                elif response.status_code == 409:
                    self.stdout.write(
                        self.style.WARNING(f'[skip] {email} already exists')
                    )
                    skipped += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f'[error] {email} — HTTP {response.status_code}: {response.text}'
                        )
                    )
                    failed += 1

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
