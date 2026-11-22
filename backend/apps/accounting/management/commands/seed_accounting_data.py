"""Idempotent demo seed for the accounting MVP (blocks 3, 4 and 5)."""

import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import AccountCatalog, AccountingEntry, FiscalPeriod
from apps.accounting.services import (
    close_period,
    create_accounting_entry,
    get_or_create_period,
)
from apps.authentication.models import CompanyMembership, User
from apps.documents.demo_data import build_demo_cfdi_files
from apps.documents.models import Document
from apps.documents.services import process_bulk_upload
from apps.tenants.models import Company
from apps.tenants.services import clone_master_sat_catalog


COMPANIES = [
    {
        "rfc": "CNO200101AB9",
        "legal_name": "Comercializadora del Norte",
        "tax_regime": Company.TaxRegime.GENERAL_PM,
    },
    {
        "rfc": "SDA210515XY1",
        "legal_name": "Servicios Digitales del Altiplano",
        "tax_regime": Company.TaxRegime.RESICO,
    },
]

USERS = [
    {
        "email": "socio@demo.mx",
        "first_name": "Sofía",
        "last_name": "Herrera",
        "role": CompanyMembership.Role.PARTNER,
        "companies": 2,
    },
    {
        "email": "auxiliar@demo.mx",
        "first_name": "Andrés",
        "last_name": "Salinas",
        "role": CompanyMembership.Role.ACCOUNTANT,
        "companies": 2,
    },
    {
        "email": "auditor@demo.mx",
        "first_name": "Alicia",
        "last_name": "Domínguez",
        "role": CompanyMembership.Role.AUDITOR,
        "companies": 2,
    },
    {
        "email": "cliente@demo.mx",
        "first_name": "Carlos",
        "last_name": "Mendoza",
        "role": CompanyMembership.Role.CLIENT,
        "companies": 1,
    },
]


def _previous_month(today):
    first_day = today.replace(day=1)
    return first_day - timedelta(days=1)


class Command(BaseCommand):
    help = (
        "Carga datos demo idempotentes: 2 empresas, 4 usuarios, membresías, "
        "catálogo SAT clonado, periodos contables, 10 CFDI 4.0 y 7 pólizas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite ejecutar el seed cuando DEBUG=False.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force"]
        if not settings.DEBUG and not force:
            raise CommandError(
                "El seed está bloqueado con DEBUG=False. "
                "Use --force para ejecutarlo de forma consciente."
            )

        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError(
                "La variable de entorno DEMO_PASSWORD es obligatoria."
            )

        companies = self._seed_companies()
        users = self._seed_users(password)
        self._seed_memberships(companies, users)
        self._seed_catalogs(companies)
        periods = self._seed_periods(companies)
        partner = users["socio@demo.mx"]

        # E-25: documents are ingested with the same service as the API while
        # the previous month is still open.
        self._seed_documents(companies, partner)

        # Block 5: journal entries are also created with the API services
        # before closing the previous month.
        self._seed_entries(companies, periods["current"], partner)

        # E-25: close the previous month only after every demo row is loaded.
        for period in periods["previous"]:
            if not period.is_closed:
                close_period(period, user=partner, ip_address="127.0.0.1")

        self._report_counts(companies)

    def _seed_companies(self):
        companies = []
        for data in COMPANIES:
            company, _created = Company.objects.update_or_create(
                rfc=data["rfc"],
                defaults={
                    "legal_name": data["legal_name"],
                    "tax_regime": data["tax_regime"],
                    "currency": "MXN",
                    "fiscal_year_start": 1,
                    "is_active": True,
                },
            )
            companies.append(company)
        return companies

    def _seed_users(self, password):
        users = {}
        for data in USERS:
            user, _created = User.objects.update_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password"])
            users[data["email"]] = user
        return users

    def _seed_memberships(self, companies, users):
        for data in USERS:
            user = users[data["email"]]
            for company in companies[: data["companies"]]:
                CompanyMembership.objects.update_or_create(
                    user=user,
                    company=company,
                    defaults={"role": data["role"], "is_active": True},
                )

    def _seed_catalogs(self, companies):
        for company in companies:
            clone_master_sat_catalog(company)

    def _seed_periods(self, companies):
        today = timezone.localdate()
        previous_date = _previous_month(today)
        periods = {"current": [], "previous": []}
        for company in companies:
            periods["current"].append(get_or_create_period(company, today))
            periods["previous"].append(
                get_or_create_period(company, previous_date)
            )
        return periods

    def _seed_entries(self, companies, current_periods, partner):
        """Create 6 balanced POSTED entries and 1 DRAFT with the API service."""
        for index, (company, period) in enumerate(
            zip(companies, current_periods)
        ):
            documents = list(
                Document.objects.filter(
                    company=company,
                    fiscal_period=period,
                ).order_by("direction", "series", "folio", "pk")
            )
            issued = [
                document
                for document in documents
                if document.direction == Document.Direction.ISSUED
            ]
            received = [
                document
                for document in documents
                if document.direction == Document.Direction.RECEIVED
            ]
            if len(issued) < 2 or not received:
                continue

            self._create_income_entry(company, partner, issued[0])
            self._create_expense_entry(company, partner, received[0])
            self._create_journal_entry(company, partner, issued[1])

            if index == 0:
                self._create_draft_entry(company, partner)

    def _account(self, company, code):
        return AccountCatalog.objects.get(company=company, code=code)

    def _entry_exists(self, company, entry_type, status, concept):
        return AccountingEntry.objects.filter(
            company=company,
            entry_type=entry_type,
            status=status,
            concept=concept,
        ).exists()

    def _document_date(self, document):
        return timezone.localtime(document.issue_date).date()

    def _save_seed_entry(
        self,
        *,
        company,
        user,
        entry_type,
        status,
        entry_date,
        concept,
        items_data,
    ):
        if self._entry_exists(company, entry_type, status, concept):
            return None
        return create_accounting_entry(
            company=company,
            user=user,
            header_data={
                "entry_type": entry_type,
                "status": status,
                "entry_date": entry_date,
                "concept": concept,
            },
            items_data=items_data,
        )

    def _create_income_entry(self, company, user, document):
        entry_date = self._document_date(document)
        concept = (
            "Seed demo · Ingreso por servicios factura "
            f"{document.series}-{document.folio}"
        )
        self._save_seed_entry(
            company=company,
            user=user,
            entry_type=AccountingEntry.EntryType.INCOME,
            status=AccountingEntry.Status.POSTED,
            entry_date=entry_date,
            concept=concept,
            items_data=[
                {
                    "account": self._account(company, "105.01"),
                    "document": document,
                    "description": "Cliente nacional",
                    "debit": document.total,
                    "credit": Decimal("0.00"),
                },
                {
                    "account": self._account(company, "401.01"),
                    "document": document,
                    "description": "Ingreso por servicios",
                    "debit": Decimal("0.00"),
                    "credit": document.subtotal,
                },
                {
                    "account": self._account(company, "207.01"),
                    "document": document,
                    "description": "IVA trasladado",
                    "debit": Decimal("0.00"),
                    "credit": document.iva_transferred,
                },
            ],
        )

    def _create_expense_entry(self, company, user, document):
        entry_date = self._document_date(document)
        concept = (
            "Seed demo · Egreso por servicios factura "
            f"{document.series}-{document.folio}"
        )
        self._save_seed_entry(
            company=company,
            user=user,
            entry_type=AccountingEntry.EntryType.EXPENSE,
            status=AccountingEntry.Status.POSTED,
            entry_date=entry_date,
            concept=concept,
            items_data=[
                {
                    "account": self._account(company, "601.38"),
                    "document": document,
                    "description": "Honorarios de servicios",
                    "debit": document.subtotal,
                    "credit": Decimal("0.00"),
                },
                {
                    "account": self._account(company, "118.01"),
                    "document": document,
                    "description": "IVA acreditable pagado",
                    "debit": document.iva_transferred,
                    "credit": Decimal("0.00"),
                },
                {
                    "account": self._account(company, "102.01.001"),
                    "document": document,
                    "description": "Pago con transferencia SPEI",
                    "debit": Decimal("0.00"),
                    "credit": document.total,
                },
            ],
        )

    def _create_journal_entry(self, company, user, document):
        entry_date = self._document_date(document)
        concept = (
            "Seed demo · Reclasificación contable factura "
            f"{document.series}-{document.folio}"
        )
        self._save_seed_entry(
            company=company,
            user=user,
            entry_type=AccountingEntry.EntryType.JOURNAL,
            status=AccountingEntry.Status.POSTED,
            entry_date=entry_date,
            concept=concept,
            items_data=[
                {
                    "account": self._account(company, "105.01"),
                    "document": document,
                    "description": "Cliente nacional",
                    "debit": document.total,
                    "credit": Decimal("0.00"),
                },
                {
                    "account": self._account(company, "401.01"),
                    "document": document,
                    "description": "Reclasificación de ingreso",
                    "debit": Decimal("0.00"),
                    "credit": document.subtotal,
                },
                {
                    "account": self._account(company, "207.01"),
                    "document": document,
                    "description": "IVA trasladado",
                    "debit": Decimal("0.00"),
                    "credit": document.iva_transferred,
                },
            ],
        )

    def _create_draft_entry(self, company, user):
        concept = "Seed demo · Borrador de póliza de diario"
        self._save_seed_entry(
            company=company,
            user=user,
            entry_type=AccountingEntry.EntryType.JOURNAL,
            status=AccountingEntry.Status.DRAFT,
            entry_date=timezone.localdate(),
            concept=concept,
            items_data=[
                {
                    "account": self._account(company, "101.01"),
                    "description": "Fondo de caja para operación",
                    "debit": Decimal("1000.00"),
                    "credit": Decimal("0.00"),
                },
                {
                    "account": self._account(company, "401.01"),
                    "description": "Ingreso pendiente de contabilizar",
                    "debit": Decimal("0.00"),
                    "credit": Decimal("1000.00"),
                },
            ],
        )

    def _seed_documents(self, companies, partner):
        """Generate and ingest 10 CFDI 4.0 files (5 per demo company)."""
        today = timezone.localdate()
        for index, company in enumerate(companies):
            counterpart = companies[(index + 1) % len(companies)]
            files = [
                SimpleUploadedFile(
                    filename,
                    content,
                    content_type="application/xml",
                )
                for filename, content in build_demo_cfdi_files(
                    company,
                    counterpart,
                    today,
                )
            ]
            result = process_bulk_upload(
                files,
                company=company,
                user=partner,
            )
            self.stdout.write(
                f"Documentos {company.rfc}: "
                f"{result['summary']['processed_count']} importados, "
                f"{result['summary']['failed_count']} omitidos."
            )

    def _report_counts(self, companies):
        company_ids = [company.pk for company in companies]
        self.stdout.write(
            "Empresas demo: "
            f"{Company.objects.filter(pk__in=company_ids).count()}, "
            "usuarios: "
            f"{User.objects.filter(email__in=[item['email'] for item in USERS]).count()}, "
            "membresías: "
            f"{CompanyMembership.objects.filter(company_id__in=company_ids).count()}, "
            "cuentas: "
            f"{AccountCatalog.objects.filter(company_id__in=company_ids).count()}, "
            "periodos: "
            f"{FiscalPeriod.objects.filter(company_id__in=company_ids).count()}, "
            "documentos: "
            f"{Document.objects.filter(company_id__in=company_ids).count()}, "
            "pólizas: "
            f"{AccountingEntry.objects.filter(company_id__in=company_ids).count()}."
        )
        self.stdout.write(self.style.SUCCESS("Seed contable v1 completado."))
