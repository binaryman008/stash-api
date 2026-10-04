from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Link, Tag
from .serializers import LinkSerializer, StatsSerializer, TagSerializer
from django.db import transaction

from .tasks import fetch_preview


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Search title, description and URL"),
            OpenApiParameter("tag", str, description="Filter by tag name"),
        ]
    )
)
class LinkViewSet(viewsets.ModelViewSet):
    serializer_class = LinkSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = Link.objects.filter(owner=self.request.user).prefetch_related("tags")
        if tag := self.request.query_params.get("tag"):
            qs = qs.filter(tags__name=tag.lower())
        if q := self.request.query_params.get("q"):
            qs = qs.filter(
                Q(title__icontains=q) | Q(description__icontains=q) | Q(url__icontains=q)
            )
        return qs

    def perform_create(self, serializer):
        link = serializer.save(owner=self.request.user)
        transaction.on_commit(lambda: fetch_preview.delay(link.id))

    def perform_update(self, serializer):
        new_url = serializer.validated_data.get("url")
        if new_url and new_url != serializer.instance.url:
            link = serializer.save(status=Link.Status.PENDING)
            transaction.on_commit(lambda: fetch_preview.delay(link.id))
        else:
            serializer.save()


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    pagination_class = None

    def get_queryset(self):
        return Tag.objects.filter(owner=self.request.user).annotate(link_count=Count("links"))


class StatsView(APIView):
    @extend_schema(responses=StatsSerializer)
    def get(self, request):
        data = Link.objects.filter(owner=request.user).aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=Link.Status.PENDING)),
            ready=Count("id", filter=Q(status=Link.Status.READY)),
            failed=Count("id", filter=Q(status=Link.Status.FAILED)),
        )
        data["tags"] = Tag.objects.filter(owner=request.user).count()
        return Response(data)
