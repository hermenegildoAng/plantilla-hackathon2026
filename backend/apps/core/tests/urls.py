from django.urls import path

from apps.core.tests import views


urlpatterns = [
    path("__tests__/success/", views.SuccessView.as_view()),
    path("__tests__/custom-message/", views.CustomMessageView.as_view()),
    path("__tests__/created/", views.CreatedView.as_view()),
    path("__tests__/validation-error/", views.ValidationErrorView.as_view()),
    path("__tests__/not-found/", views.NotFoundView.as_view()),
    path("__tests__/server-error/", views.ServerErrorView.as_view()),
]
