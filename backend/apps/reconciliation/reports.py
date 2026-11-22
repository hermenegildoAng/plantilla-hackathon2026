"""ORM-only report calculations: trial balance and executive summary [E-21]."""

from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.accounting.models import (
    AccountCatalog,
    AccountingEntry,
    AccountingEntryItem,
    FiscalPeriod,
)
from apps.documents.models import Document


MONEY_FIELD = DecimalField(max_digits=16, decimal_places=2)
MONEY_QUANTUM = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value):
    if value is None:
        return ZERO
    return Decimal(value).quantize(MONEY_QUANTUM)


def _period_payload(period):
    return {
        "id": period.pk,
        "year": period.year,
        "month": period.month,
        "label": f"{period.year}-{period.month:02d}",
        "is_closed": period.is_closed,
    }


def _fiscal_year_start(company, period):
    start_month = company.fiscal_year_start or 1
    start_year = (
        period.year
        if period.month >= start_month
        else period.year - 1
    )
    return start_year, start_month


def _previous_period_ids(company, period):
    start_year, start_month = _fiscal_year_start(company, period)
    return list(
        FiscalPeriod.objects.filter(company=company)
        .filter(
            Q(year__gt=start_year)
            | Q(year=start_year, month__gte=start_month)
        )
        .filter(
            Q(year__lt=period.year)
            | Q(year=period.year, month__lt=period.month)
        )
        .values_list("pk", flat=True)
    )


def _aggregate_items(company, period_ids):
    if not period_ids:
        return {}
    rows = (
        AccountingEntryItem.objects.filter(
            company=company,
            entry__status=AccountingEntry.Status.POSTED,
            entry__fiscal_period_id__in=period_ids,
        )
        .values("account_id")
        .annotate(
            total_debit=Coalesce(
                Sum("debit"),
                Value(ZERO),
                output_field=MONEY_FIELD,
            ),
            total_credit=Coalesce(
                Sum("credit"),
                Value(ZERO),
                output_field=MONEY_FIELD,
            ),
        )
    )
    return {row["account_id"]: row for row in rows}


def build_trial_balance(company, period):
    """Return the trial balance for one fiscal period.

    Opening balances accumulate POSTED items from previous periods of the same
    fiscal year. Closing balances are presented according to account nature.
    """
    previous_ids = _previous_period_ids(company, period)
    opening_rows = _aggregate_items(company, previous_ids)
    current_rows = _aggregate_items(company, [period.pk])

    account_ids = set(opening_rows) | set(current_rows)
    accounts = {
        account.pk: account
        for account in AccountCatalog.objects.filter(
            company=company,
            pk__in=account_ids,
        ).order_by("code")
    }

    rows = []
    total_opening = ZERO
    total_debit = ZERO
    total_credit = ZERO
    total_closing = ZERO

    for account_id in sorted(
        account_ids,
        key=lambda pk: accounts[pk].code if pk in accounts else "",
    ):
        account = accounts.get(account_id)
        if account is None:
            continue

        opening = opening_rows.get(account_id, {})
        current = current_rows.get(account_id, {})
        opening_debit = _money(opening.get("total_debit"))
        opening_credit = _money(opening.get("total_credit"))
        period_debit = _money(current.get("total_debit"))
        period_credit = _money(current.get("total_credit"))

        raw_opening = opening_debit - opening_credit
        raw_closing = raw_opening + period_debit - period_credit

        if account.nature == AccountCatalog.Nature.DEBIT:
            opening_balance = raw_opening
            closing_balance = raw_closing
        else:
            opening_balance = -raw_opening
            closing_balance = -raw_closing

        if (
            opening_balance == ZERO
            and period_debit == ZERO
            and period_credit == ZERO
        ):
            continue

        rows.append(
            {
                "account_id": account.pk,
                "sat_group_code": account.sat_group_code,
                "code": account.code,
                "name": account.name,
                "nature": account.nature,
                "opening_balance": opening_balance,
                "total_debit": period_debit,
                "total_credit": period_credit,
                "closing_balance": closing_balance,
            }
        )
        total_opening += opening_balance
        total_debit += period_debit
        total_credit += period_credit
        total_closing += closing_balance

    return {
        "period": _period_payload(period),
        "accounts": rows,
        "totals": {
            "opening_balance": total_opening,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": total_closing,
            "difference": total_debit - total_credit,
        },
    }


def build_executive_summary(company, period):
    """Return the preliminary IVA/ISR and income/expense totals for a period."""
    totals = Document.objects.filter(
        company=company,
        fiscal_period=period,
    ).aggregate(
        total_iva_transferred=Coalesce(
            Sum(
                "iva_transferred",
                filter=Q(direction=Document.Direction.ISSUED),
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
        total_iva_creditable=Coalesce(
            Sum(
                "iva_transferred",
                filter=Q(direction=Document.Direction.RECEIVED),
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
        total_iva_retained=Coalesce(
            Sum(
                "iva_retained",
                filter=Q(direction=Document.Direction.RECEIVED),
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
        total_isr_retained=Coalesce(
            Sum(
                "isr_retained",
                filter=Q(direction=Document.Direction.RECEIVED),
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
        total_income=Coalesce(
            Sum(
                "total",
                filter=Q(direction=Document.Direction.ISSUED),
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
        total_expense=Coalesce(
            Sum(
                "total",
                filter=Q(direction=Document.Direction.RECEIVED),
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
    )

    return {
        "period": _period_payload(period),
        "iva_transferred": _money(totals["total_iva_transferred"]),
        "iva_creditable": _money(totals["total_iva_creditable"]),
        "iva_retained": _money(totals["total_iva_retained"]),
        "isr_retained": _money(totals["total_isr_retained"]),
        "income_total": _money(totals["total_income"]),
        "expense_total": _money(totals["total_expense"]),
    }


def reduce_executive_summary_for_client(summary):
    """CLIENT only receives income/expense and IVA totals [E-21]."""
    return {
        "period": summary["period"],
        "iva_transferred": summary["iva_transferred"],
        "iva_creditable": summary["iva_creditable"],
        "income_total": summary["income_total"],
        "expense_total": summary["expense_total"],
    }
