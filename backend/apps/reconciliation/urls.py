from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.reconciliation.views import (
    BankMovementViewSet,
    ExecutiveSummaryView,
    TrialBalanceView,
)


app_name = "reconciliation"

router = SimpleRouter()
router.register(
    "reconciliation/movements",
    BankMovementViewSet,
    basename="bank-movement",
)

urlpatterns = [
    path(
        "reports/trial-balance/",
        TrialBalanceView.as_view(),
        name="trial-balance",
    ),
    path(
        "reports/executive-summary/",
        ExecutiveSummaryView.as_view(),
        name="executive-summary",
    ),
    path("", include(router.urls)),
]
