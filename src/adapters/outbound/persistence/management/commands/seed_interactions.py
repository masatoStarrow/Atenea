"""
Management command: seed_interactions

Creates sample interactions in Venus (interactions-service) by POSTing
to its /api/v1/interactions/ endpoint.

Requires:
  - Artemisa running (to fetch client UUIDs)
  - Venus running (to accept interaction POSTs)
  - Users and clients already seeded
"""

import asyncio
import json

from django.core.management.base import BaseCommand

from src.adapters.outbound.http_client.interactions_client import InteractionsServiceClient
from src.adapters.outbound.http_client.users_client import UsersServiceClient
from src.adapters.outbound.persistence.models.user_model import User
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


# Interaction templates — client_id will be filled dynamically
SEED_INTERACTIONS = [
    # ── Acme Corporation (index 0) ───────────────────────────────────
    {
        "type": "call",
        "channel": "phone",
        "subject": "Llamada de seguimiento contrato anual",
        "status": "resolved",
        "notes": "Se confirmó renovación del contrato por 12 meses.",
        "outcome": "Contrato renovado",
        "interaction_date": "2026-02-15T10:30:00Z",
        "duration_minutes": 25,
        "tags": ["renovacion", "contrato"],
        "_client_idx": 0,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Envío de propuesta comercial Q2",
        "status": "pending",
        "notes": "Propuesta enviada con descuento del 15% por fidelidad.",
        "interaction_date": "2026-03-01T09:00:00Z",
        "follow_up_date": "2026-03-15T09:00:00Z",
        "tags": ["propuesta", "descuento"],
        "_client_idx": 0,
        "_agent_email": "admin@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Reunión de presentación nuevos servicios",
        "status": "resolved",
        "notes": "Presentación bien recibida. Interesados en módulo premium.",
        "internal_notes": "Cliente tiene presupuesto aprobado para Q3.",
        "outcome": "Agendar demo para abril",
        "interaction_date": "2026-02-20T14:00:00Z",
        "duration_minutes": 60,
        "tags": ["reunion", "premium"],
        "_client_idx": 0,
        "_agent_email": "soporte@crm.com",
    },
    # ── Globex Industries (index 1) ──────────────────────────────────
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "Problema con facturación duplicada",
        "status": "in_progress",
        "notes": "El cliente reporta dos cobros en el mismo periodo.",
        "internal_notes": "Revisar con contabilidad antes de responder.",
        "interaction_date": "2026-03-02T11:00:00Z",
        "tags": ["facturacion", "urgente"],
        "_client_idx": 1,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "note",
        "channel": "platform",
        "subject": "Nota interna sobre renovación Globex",
        "status": "resolved",
        "notes": "Cliente en proceso de evaluación de competidores.",
        "internal_notes": "Riesgo medio de churn. Ofrecer descuento si amenaza con irse.",
        "interaction_date": "2026-02-28T16:00:00Z",
        "tags": ["churn", "renovacion"],
        "_client_idx": 1,
        "_agent_email": "admin@crm.com",
    },
    # ── Stark Enterprises (index 2) ──────────────────────────────────
    {
        "type": "call",
        "channel": "phone",
        "subject": "Contacto inicial — interés en plataforma CRM",
        "status": "resolved",
        "notes": "Primer contacto. Interesados en plan enterprise.",
        "outcome": "Enviar brochure y agendar demo",
        "interaction_date": "2026-01-15T10:00:00Z",
        "duration_minutes": 15,
        "tags": ["prospecto", "enterprise"],
        "_client_idx": 2,
        "_agent_email": "admin@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Seguimiento propuesta Stark Enterprises",
        "status": "pending",
        "notes": "Enviada propuesta personalizada. Esperando respuesta del CTO.",
        "interaction_date": "2026-02-01T09:30:00Z",
        "follow_up_date": "2026-04-01T09:00:00Z",
        "tags": ["propuesta", "enterprise"],
        "_client_idx": 2,
        "_agent_email": "soporte@crm.com",
    },
    # ── Umbrella Corp (index 4 — skipping Wayne=inactive) ─────────────
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Revisión trimestral de resultados",
        "status": "closed",
        "notes": "Revisión Q4 completada. Métricas positivas.",
        "outcome": "Mantener plan actual",
        "interaction_date": "2026-01-20T15:00:00Z",
        "duration_minutes": 45,
        "tags": ["revision", "trimestral"],
        "_client_idx": 4,
        "_agent_email": "admin@crm.com",
    },
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "Solicitud de soporte técnico — integración API",
        "status": "pending",
        "notes": "Necesitan ayuda para integrar webhook de notificaciones.",
        "interaction_date": "2026-03-03T08:00:00Z",
        "follow_up_date": "2026-03-10T08:00:00Z",
        "tags": ["soporte", "api", "integracion"],
        "_client_idx": 4,
        "_agent_email": "soporte@crm.com",
    },
    # ── Extra: Wayne Technologies (index 3, inactive client) ──────────
    {
        "type": "call",
        "channel": "whatsapp",
        "subject": "Intento de reactivación de cuenta Wayne",
        "status": "pending",
        "notes": "Se contactó para evaluar posible reactivación de servicios.",
        "interaction_date": "2026-03-01T12:00:00Z",
        "follow_up_date": "2026-03-20T12:00:00Z",
        "tags": ["reactivacion"],
        "_client_idx": 3,
        "_agent_email": "admin@crm.com",
    },
]


class Command(BaseCommand):
    help = (
        'Seeds Venus (interactions-service) with sample interactions. '
        'Requires users, clients, and Venus to be running.'
    )

    def handle(self, *args, **options):
        interactions_client = InteractionsServiceClient()
        users_client = UsersServiceClient()

        # 1. Get admin user from Gateway DB for auth headers
        try:
            admin_user = User.objects.get(email='admin@crm.com')
            admin_id = str(admin_user.id)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                'Admin user not found. Run seed_users first.'
            ))
            return

        # 2. Build agent email → UUID mapping from Gateway DB
        agent_map = {}
        for u in User.objects.filter(email__in=[
            'admin@crm.com', 'soporte@crm.com', 'comercial@crm.com'
        ]):
            agent_map[u.email] = str(u.id)

        # 3. Fetch client list from Artemisa to get UUIDs
        try:
            response = _run_async(
                users_client.forward_request(
                    method='GET',
                    path='/clients?page_size=100',
                    user_id=admin_id,
                    user_role='admin',
                )
            )
        except ServiceUnavailableError:
            self.stderr.write(self.style.ERROR(
                'Artemisa (users-service) is not available. Seed clients first.'
            ))
            return

        if response.status_code != 200:
            self.stderr.write(self.style.ERROR(
                f'Failed to fetch clients: HTTP {response.status_code}'
            ))
            return

        clients_data = response.json().get('data', {}).get('items', [])
        if not clients_data:
            self.stderr.write(self.style.ERROR(
                'No clients found in Artemisa. Run seed_clients first.'
            ))
            return

        # Sort by company name for predictable index mapping
        clients_data.sort(key=lambda c: c.get('company', ''))
        self.stdout.write(self.style.SUCCESS(
            f'Found {len(clients_data)} clients in Artemisa'
        ))

        # 4. Create interactions
        created = 0
        skipped = 0
        failed = 0

        for interaction in SEED_INTERACTIONS:
            client_idx = interaction.pop('_client_idx')
            agent_email = interaction.pop('_agent_email')

            if client_idx >= len(clients_data):
                self.stdout.write(self.style.WARNING(
                    f'[skip] Client index {client_idx} out of range'
                ))
                skipped += 1
                continue

            client_id = clients_data[client_idx]['id']
            agent_id = agent_map.get(agent_email, admin_id)

            interaction['client_id'] = client_id
            body = json.dumps(interaction).encode()

            try:
                resp = _run_async(
                    interactions_client.forward_request(
                        method='POST',
                        path='/interactions/',
                        body=body,
                        user_id=agent_id,
                        user_role='admin',
                    )
                )

                if resp.status_code == 201:
                    self.stdout.write(self.style.SUCCESS(
                        f'[created] {interaction["subject"][:50]}...'
                    ))
                    created += 1
                else:
                    self.stdout.write(self.style.ERROR(
                        f'[error] HTTP {resp.status_code}: {resp.text[:120]}'
                    ))
                    failed += 1

            except ServiceUnavailableError:
                self.stdout.write(self.style.ERROR(
                    f'[error] Venus unavailable — {interaction["subject"][:40]}'
                ))
                failed += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Seed completed — created: {created}, skipped: {skipped}, failed: {failed}'
        ))
