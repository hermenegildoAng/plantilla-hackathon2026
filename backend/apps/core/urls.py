from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.core.views import AuditLogViewSet, HealthView


app_name = "core"

router = SimpleRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("", include(router.urls)),
]
