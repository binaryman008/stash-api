import factory

from accounts.tests.factories import UserFactory
from links.models import Link, Tag


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"tag{n}")


class LinkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Link

    owner = factory.SubFactory(UserFactory)
    url = factory.Sequence(lambda n: f"https://example.com/article-{n}")
