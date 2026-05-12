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
    {
        "type": "call",
        "channel": "phone",
        "subject": "Propuesta plan Premium enviada",
        "status": "resolved",
        "notes": "Se presentaron beneficios del plan Premium. Manager interesado en descuento por volumen.",
        "internal_notes": "Manager pregunta por descuento por volumen. Presupuesto aprobado para Q3.",
        "outcome": "Agendar llamada de seguimiento",
        "interaction_date": "2026-04-01T09:30:00Z",
        "duration_minutes": 30,
        "_client_idx": 5,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "Problema con pagos demorados",
        "status": "resolved",
        "notes": "El restaurante reporta que los pagos tardan mas de 72 horas en acreditarse.",
        "internal_notes": "Problema en el gateway de pagos. Escalado a equipo de infraestructura.",
        "outcome": "Ticket resuelto — gateway actualizado",
        "interaction_date": "2026-04-03T14:00:00Z",
        "duration_minutes": 45,
        "_client_idx": 5,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Seguimiento propuesta Premium",
        "status": "pending",
        "notes": "Ana llama para dar seguimiento a la propuesta Premium enviada la semana pasada. Manager acepta el plan.",
        "internal_notes": "Cotizacion aceptada, pendiente firma. Enviar contrato por DocuSign.",
        "interaction_date": "2026-04-08T09:10:00Z",
        "follow_up_date": "2099-06-01T09:00:00Z",
        "duration_minutes": 20,
        "_client_idx": 5,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Cotizacion firmada — Plan Premium Sushi Express",
        "status": "closed",
        "notes": "Se recibio la cotizacion firmada. Plan Premium activado.",
        "outcome": "Plan Premium activado exitosamente",
        "interaction_date": "2026-04-10T11:00:00Z",
        "_client_idx": 5,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "Problema con pagos — segunda incidencia",
        "status": "in_progress",
        "notes": "El Sushi Express reporta nuevamente demoras en pagos. Mismo sintoma que ticket anterior.",
        "internal_notes": "Posible regresion del fix anterior. Investigar con equipo de infra.",
        "interaction_date": "2026-04-15T15:00:00Z",
        "follow_up_date": "2099-04-20T09:00:00Z",
        "_client_idx": 5,
        "_agent_email": "soporte2@crm.com",
    },
    {
        "type": "note",
        "channel": "platform",
        "subject": "Nota interna — evaluacion upselling",
        "status": "pending",
        "notes": "Sushi Express tiene potencial para migrar a plan Enterprise en Q3. Facturacion mensual superior a $50k.",
        "internal_notes": "Hablar con manager sobre Enterprise en la proxima revision trimestral.",
        "interaction_date": "2026-04-16T10:00:00Z",
        "_client_idx": 5,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Kickoff partnership Didi Food — CRM onboarding",
        "status": "closed",
        "notes": "Reunion inicial para integrar restaurantes Didi Food al CRM. Se definieron objetivos Q2.",
        "outcome": "Onboarding iniciado — 200 restaurantes objetivo",
        "interaction_date": "2026-03-10T10:00:00Z",
        "duration_minutes": 90,
        "_client_idx": 2,
        "_agent_email": "admin@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Seguimiento primer mes de partnership",
        "status": "resolved",
        "notes": "Primer mes positivo. 85% de restaurantes activos en la plataforma. Buenos indicadores de adopcion.",
        "outcome": "Continuar con plan actual",
        "interaction_date": "2026-04-10T11:00:00Z",
        "duration_minutes": 25,
        "_client_idx": 2,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Reporte mensual de adopcion — Marzo 2026",
        "status": "resolved",
        "notes": "Envio de reporte con metricas de adopcion: 170 restaurantes activos, 12% churn, NPS 72.",
        "interaction_date": "2026-04-05T10:00:00Z",
        "_client_idx": 2,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Presentacion Starrow para equipo comercial NU",
        "status": "resolved",
        "notes": "Demo del CRM para el equipo de account management de NU. Interes en modulo de interacciones.",
        "internal_notes": "CTO impresionado. Pidieron propuesta para 500 agentes.",
        "outcome": "Enviar propuesta enterprise",
        "interaction_date": "2026-03-20T14:00:00Z",
        "duration_minutes": 60,
        "_client_idx": 3,
        "_agent_email": "admin@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Propuesta Enterprise NU Bank — 500 agentes",
        "status": "in_progress",
        "notes": "Propuesta enviada con pricing escalonado. Incluye SSO, API publica y soporte prioritario.",
        "internal_notes": "Precio propuesto: $12/agente/mes con compromiso anual. Margen del 40%.",
        "interaction_date": "2026-03-28T09:00:00Z",
        "follow_up_date": "2099-04-15T10:00:00Z",
        "_client_idx": 3,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "ticket",
        "channel": "email",
        "subject": "Consulta sobre integracion SSO con Azure AD",
        "status": "pending",
        "notes": "El equipo de seguridad de NU solicita informacion sobre integracion SSO/SAML.",
        "interaction_date": "2026-04-12T16:00:00Z",
        "follow_up_date": "2099-04-18T09:00:00Z",
        "_client_idx": 3,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Contacto inicial — Burger House interesado en CRM",
        "status": "resolved",
        "notes": "Primer contacto. Cadena de 15 restaurantes. Quieren centralizar gestion de proveedores.",
        "outcome": "Enviar brochure y agendar demo",
        "interaction_date": "2026-03-05T10:00:00Z",
        "duration_minutes": 15,
        "_client_idx": 0,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Demo presencial Starrow — Burger House central",
        "status": "pending",
        "notes": "Demo del sistema para el equipo de operaciones. Mostrar modulo de interacciones y metricas.",
        "interaction_date": "2026-04-20T11:00:00Z",
        "follow_up_date": "2099-04-25T09:00:00Z",
        "_client_idx": 0,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "call",
        "channel": "whatsapp",
        "subject": "Consulta sobre plan Basic",
        "status": "resolved",
        "notes": "Cafe de Origen pregunta por el plan Basic. Quieren gestionar sus 3 proveedores de cafe.",
        "outcome": "Enviar enlace de registro",
        "interaction_date": "2026-04-05T09:00:00Z",
        "duration_minutes": 10,
        "_client_idx": 1,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "No pueden cargar adjuntos en interacciones",
        "status": "in_progress",
        "notes": "Reportan error 413 al intentar subir PDFs grandes.",
        "internal_notes": "Verificar limite de 10MB. Posible que esten subiendo archivos >10MB.",
        "interaction_date": "2026-04-14T13:00:00Z",
        "_client_idx": 1,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Renovacion contrato anual — Pizza Tradizionale",
        "status": "resolved",
        "notes": "Contrato renovado por 12 meses mas. Se incluyo descuento del 10% por lealtad.",
        "outcome": "Contrato renovado",
        "interaction_date": "2026-02-15T10:00:00Z",
        "_client_idx": 4,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "note",
        "channel": "platform",
        "subject": "Evaluacion de satisfaccion — Q1 2026",
        "status": "closed",
        "notes": "Cliente satisfecho con el servicio. NPS 85. Referira a otros restaurantes italianos.",
        "outcome": "Cliente promotor",
        "interaction_date": "2026-03-30T16:00:00Z",
        "_client_idx": 4,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Prospecto — Wok & Roll interesado en Starrow",
        "status": "pending",
        "notes": "Contacto por LinkedIn. Cadena de comida asiatica con 8 locales. Quieren demo.",
        "interaction_date": "2026-04-18T14:30:00Z",
        "follow_up_date": "2099-04-22T10:00:00Z",
        "duration_minutes": 12,
        "_client_idx": 7,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Intento de reactivacion — Tacos El Pastor",
        "status": "pending",
        "notes": "Se contacto para evaluar reactivacion. No mostraron interes por el momento.",
        "interaction_date": "2026-03-25T12:00:00Z",
        "follow_up_date": "2099-06-01T10:00:00Z",
        "_client_idx": 6,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Revision trimestral Q1 — Pizza Tradizionale",
        "status": "closed",
        "notes": "Revision de metricas Q1: 98% uptime, NPS 85, 0 tickets criticos. Cliente muy satisfecho.",
        "internal_notes": "Oportunidad de upselling a plan Premium. Actualmente en Basic.",
        "outcome": "Cliente renovado y satisfecho",
        "interaction_date": "2026-03-15T11:00:00Z",
        "duration_minutes": 45,
        "_client_idx": 4,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Brochure y pricing — Burger House",
        "status": "resolved",
        "notes": "Envio de brochure comercial con planes y precios para los 15 restaurantes de Burger House.",
        "internal_notes": "Interes en plan Business para 10 locales + Basic para 5. Enviar propuesta personalizada.",
        "outcome": "Brochure entregado — agendar demo",
        "interaction_date": "2026-03-12T10:00:00Z",
        "_client_idx": 0,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Workshop integracion tecnica — Didi Food",
        "status": "resolved",
        "notes": "Sesion de trabajo con equipo tecnico de Didi para definir integracion API. Se mapearon endpoints criticos.",
        "internal_notes": "Necesitan webhook para eventos de restaurantes. Definir schema en siguiente sprint.",
        "outcome": "Integracion API definida — sprint planificado",
        "interaction_date": "2026-03-25T15:00:00Z",
        "duration_minutes": 120,
        "_client_idx": 2,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "Onboarding restaurante — error en importacion de datos",
        "status": "resolved",
        "notes": "Restaurante 'La Parrilla MX' no aparece en el listado tras importar CSV. Datos cargados manualmente como workaround.",
        "internal_notes": "Bug en parser CSV con caracteres especiales. Fix pendiente para proxima version.",
        "outcome": "Datos cargados manualmente — bug reportado",
        "interaction_date": "2026-04-02T09:30:00Z",
        "_client_idx": 2,
        "_agent_email": "soporte2@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Soporte onboarding — Cafe de Origen",
        "status": "resolved",
        "notes": "Cafe de Origen necesito ayuda para configurar sus 3 proveedores en el sistema. Se guio paso a paso.",
        "internal_notes": "UX de alta de proveedores confusa. Considerar simplificar en proxima iteracion.",
        "outcome": "Proveedores configurados exitosamente",
        "interaction_date": "2026-04-08T10:30:00Z",
        "duration_minutes": 20,
        "_client_idx": 1,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Documentacion SSO SAML — NU Bank",
        "status": "resolved",
        "notes": "Envio de documentacion tecnica completa sobre integracion SSO/SAML con Azure AD. Incluye diagramas de flujo.",
        "internal_notes": "CTO de NU confirmo recepcion. Equipo de seguridad evaluando. Plazo de respuesta: 5 dias habiles.",
        "outcome": "Documentacion entregada — en revision por equipo de seguridad",
        "interaction_date": "2026-04-15T08:30:00Z",
        "_client_idx": 3,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "Fix pagos regresion — confirmacion Sushi Express",
        "status": "resolved",
        "notes": "Se confirmo que el fix de la regresion de pagos esta funcionando correctamente. Pagos acreditados en menos de 24h.",
        "internal_notes": "Root cause: cache del gateway no invalidaba correctamente. Fix deployado en v2.4.1.",
        "outcome": "Regresion resuelta — gateway actualizado a v2.4.1",
        "interaction_date": "2026-04-17T11:00:00Z",
        "_client_idx": 5,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "ticket",
        "channel": "platform",
        "subject": "Adjuntos — fix confirmado para Cafe de Origen",
        "status": "resolved",
        "notes": "Se incremento limite de upload a 25MB. Cliente confirmo que puede subir PDFs sin problemas.",
        "internal_notes": "Se agrego validacion de tipo de archivo y compresion automatica para archivos >15MB.",
        "outcome": "Limite incrementado — upload funcional",
        "interaction_date": "2026-04-17T14:00:00Z",
        "_client_idx": 1,
        "_agent_email": "soporte@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Negociacion contrato Enterprise — NU Bank",
        "status": "in_progress",
        "notes": "Llamada con director comercial de NU. Negociando volumen por 500 agentes. Piden 20% de descuento sobre precio lista.",
        "internal_notes": "Contrapropuesta: 15% descuento con compromiso de 24 meses. Margen del 30%. Aprobado por gerencia.",
        "interaction_date": "2026-04-18T16:00:00Z",
        "follow_up_date": "2099-04-25T10:00:00Z",
        "duration_minutes": 40,
        "_client_idx": 3,
        "_agent_email": "comercial@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Revision trimestral Q2 — Sushi Express",
        "status": "closed",
        "notes": "Revision completa: 100% adopcion del modulo de interacciones, NPS 78. Manager conforme con Premium.",
        "internal_notes": "Cliente candidato a Enterprise en Q3. Preparar propuesta con SLA dedicado.",
        "outcome": "Revision completada — cliente promotor",
        "interaction_date": "2026-04-20T15:00:00Z",
        "duration_minutes": 60,
        "_client_idx": 5,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "ticket",
        "channel": "email",
        "subject": "Solicitud auditoria de seguridad — NU Bank",
        "status": "pending",
        "notes": "Equipo de compliance de NU solicita auditoria de seguridad del CRM. Requieren certificacion SOC 2.",
        "internal_notes": "Evaluar si podemos proporcionar reporte de seguridad. Consultar con equipo legal.",
        "interaction_date": "2026-04-22T09:00:00Z",
        "follow_up_date": "2099-04-30T10:00:00Z",
        "_client_idx": 3,
        "_agent_email": "soporte2@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Evaluacion enterprise tier — Didi Food",
        "status": "pending",
        "notes": "Reunion para evaluar migracion a plan Enterprise con SLA dedicado y API publica para 200+ restaurantes.",
        "internal_notes": "Preparar caso de estudio con metricas de los primeros 2 meses. Enfocar en ROI.",
        "interaction_date": "2026-04-22T14:00:00Z",
        "follow_up_date": "2099-04-28T10:00:00Z",
        "duration_minutes": 60,
        "_client_idx": 2,
        "_agent_email": "admin@crm.com",
    },
    {
        "type": "call",
        "channel": "whatsapp",
        "subject": "Segundo intento de reactivacion — Tacos El Pastor",
        "status": "pending",
        "notes": "Segundo intento de reactivacion. Se ofrece plan Basic con 30% de descuento por 3 meses. Pendiente respuesta.",
        "internal_notes": "Ultimo intento. Si no responden en 2 semanas, marcar como churn definitivo.",
        "interaction_date": "2026-04-22T16:00:00Z",
        "follow_up_date": "2099-05-06T10:00:00Z",
        "duration_minutes": 8,
        "_client_idx": 6,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "call",
        "channel": "phone",
        "subject": "Negociacion post-demo — Burger House",
        "status": "pending",
        "notes": "Llamada programada post-demo para discutir pricing y condiciones comerciales para los 15 locales.",
        "internal_notes": "Si cierran, seria el cliente mas grande por numero de locales. Preparar descuento por volumen.",
        "interaction_date": "2026-04-25T10:00:00Z",
        "follow_up_date": "2099-04-30T10:00:00Z",
        "duration_minutes": 30,
        "_client_idx": 0,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "email",
        "channel": "email",
        "subject": "Propuesta upselling Premium — Pizza Tradizionale",
        "status": "pending",
        "notes": "Propuesta enviada para migrar de plan Basic a Premium. Incluye modulo de reportes avanzados y API publica.",
        "internal_notes": "Precio propuesto: upgrade con 15% de descuento por lealtad. Renovacion en 2 meses.",
        "interaction_date": "2026-04-25T09:00:00Z",
        "follow_up_date": "2099-05-02T10:00:00Z",
        "_client_idx": 4,
        "_agent_email": "comercial2@crm.com",
    },
    {
        "type": "meeting",
        "channel": "in_person",
        "subject": "Demo Starrow — Wok & Roll",
        "status": "pending",
        "notes": "Demo programada para equipo directivo de Wok & Roll. 8 locales, buscan centralizar gestion de clientes.",
        "internal_notes": "Contacto vino por LinkedIn. Alto interes. Preparar demo con datos de comida asiatica.",
        "interaction_date": "2026-04-28T11:00:00Z",
        "follow_up_date": "2099-05-05T10:00:00Z",
        "duration_minutes": 45,
        "_client_idx": 7,
        "_agent_email": "comercial@crm.com",
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
            'admin@crm.com', 'soporte@crm.com', 'soporte2@crm.com',
            'comercial@crm.com', 'comercial2@crm.com',
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
