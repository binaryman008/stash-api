from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import LinkViewSet, StatsView, TagViewSet

router = DefaultRouter()
router.register("links", LinkViewSet, basename="link")
router.register("tags", TagViewSet, basename="tag")

urlpatterns = [*router.urls, path("stats/", StatsView.as_view(), name="stats")]
