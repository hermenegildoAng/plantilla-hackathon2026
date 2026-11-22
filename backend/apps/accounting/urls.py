from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.accounting.views import (
    AccountCatalogViewSet,
    AccountingEntryViewSet,
    FiscalPeriodViewSet,
)


app_name = "accounting"

router = SimpleRouter()
router.register("accounts", AccountCatalogViewSet, basename="account")
router.register("entries", AccountingEntryViewSet, basename="entry")
router.register("periods", FiscalPeriodViewSet, basename="fiscal-period")

urlpatterns = [
    path("", include(router.urls)),
]
