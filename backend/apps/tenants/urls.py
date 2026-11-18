from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.tenants.views import CompanyViewSet


app_name = "tenants"

router = SimpleRouter()
router.register("companies", CompanyViewSet, basename="company")

urlpatterns = [
    path("", include(router.urls)),
]
