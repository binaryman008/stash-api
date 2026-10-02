from rest_framework import serializers

from .models import Link, Tag


class TagNamesField(serializers.ListField):
    """Reads and writes tags as plain strings: ["django", "aws"]."""

    child = serializers.CharField(max_length=50)

    def to_representation(self, value):
        return [tag.name for tag in value.all()]


class LinkSerializer(serializers.ModelSerializer):
    tags = TagNamesField(required=False)

    class Meta:
        model = Link
        fields = [
            "id",
            "url",
            "title",
            "description",
            "image_url",
            "reading_minutes",
            "status",
            "tags",
            "created_at",
        ]
        read_only_fields = [
            "title",
            "description",
            "image_url",
            "reading_minutes",
            "status",
            "created_at",
        ]

    def validate_url(self, value):
        qs = Link.objects.filter(owner=self.context["request"].user, url=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("You already saved this link.")
        return value

    def create(self, validated_data):
        names = validated_data.pop("tags", [])
        link = Link.objects.create(**validated_data)
        self._set_tags(link, names)
        return link

    def update(self, instance, validated_data):
        names = validated_data.pop("tags", None)
        instance = super().update(instance, validated_data)
        if names is not None:
            self._set_tags(instance, names)
        return instance

    def _set_tags(self, link, names):
        cleaned = {n.strip().lower() for n in names if n.strip()}
        tags = [Tag.objects.get_or_create(owner=link.owner, name=n)[0] for n in cleaned]
        link.tags.set(tags)


class TagSerializer(serializers.ModelSerializer):
    link_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "link_count"]


class StatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    ready = serializers.IntegerField()
    failed = serializers.IntegerField()
    tags = serializers.IntegerField()
