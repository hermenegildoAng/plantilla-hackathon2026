from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.documents.views import DocumentViewSet


app_name = "documents"

router = SimpleRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("", include(router.urls)),
]
