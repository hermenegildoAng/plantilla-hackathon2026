from types import SimpleNamespace
from unittest.mock import Mock

from apps.tenants.mixins import TenantQuerySetMixin


class BaseView:
    def __init__(self, queryset):
        self.base_queryset = queryset

    def get_queryset(self):
        return self.base_queryset


class TenantView(TenantQuerySetMixin, BaseView):
    pass


def test_tenant_queryset_mixin_filters_by_request_company():
    base_queryset = Mock(name="base_queryset")
    filtered = Mock(name="filtered_queryset")
    base_queryset.filter.return_value = filtered
    company = SimpleNamespace(id=99)

    view = TenantView(base_queryset)
    view.request = SimpleNamespace(company=company)

    assert view.get_queryset() is filtered
    base_queryset.filter.assert_called_once_with(company=company)


def test_tenant_queryset_mixin_injects_company_on_create():
    company = SimpleNamespace(id=99)
    serializer = Mock()

    view = TenantView(Mock())
    view.request = SimpleNamespace(company=company)

    view.perform_create(serializer)

    serializer.save.assert_called_once_with(company=company)
