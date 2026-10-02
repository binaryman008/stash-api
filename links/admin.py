from django.contrib import admin

from .models import Link, Tag


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ["url", "owner", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["url", "title"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "owner"]
