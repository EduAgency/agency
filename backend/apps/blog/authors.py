"""Author identity.

A byline of `user.get_full_name()` is enough to say who wrote something and not
enough to make anyone believe them — which matters more here than on most blogs,
because the whole pitch is that we say things other agents will not.

The SEO value is concrete and worth naming: `sameAs` links in `Person` JSON-LD
are how a search engine connects a byline to a real identity elsewhere on the
web. That is what separates an authored article from an anonymous one in the eyes
of the thing we are asking to rank us.

See docs/blog-system.md §2.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel


class AuthorProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="author_profile"
    )

    display_name = models.CharField(
        max_length=120, help_text="The byline. Not necessarily the account name."
    )
    slug = models.SlugField(max_length=140, unique=True, help_text="Used for /blog/author/<slug>.")
    headline = models.CharField(
        max_length=140, blank=True, help_text='The line under the name — "Admissions lead".'
    )
    bio = models.TextField(
        blank=True, help_text="A paragraph. Markdown, rendered through the same sanitiser as post bodies."
    )
    credentials = models.CharField(
        max_length=200,
        blank=True,
        help_text=(
            "Qualifications, if there are any. Checked against the house style — an author bio is "
            "the most tempting place on the site to invent one."
        ),
    )

    avatar = models.ImageField(upload_to="blog/authors/", null=True, blank=True, max_length=500)
    avatar_alt = models.CharField(max_length=160, blank=True)

    website = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    x_url = models.URLField(blank=True, verbose_name="X / Twitter URL")

    is_public = models.BooleanField(
        default=False,
        help_text="An author page exists only when the author has opted into having one.",
    )
    show_in_directory = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_name",)

    def __str__(self) -> str:
        return self.display_name

    def clean(self):
        if self.avatar and not self.avatar_alt.strip():
            raise ValidationError(
                {"avatar_alt": "Describe the photo. A byline portrait carries information."}
            )
        if self.is_public and not self.bio.strip():
            raise ValidationError(
                {"bio": "A public author page with no bio is a thin page. Write a paragraph or keep it private."}
            )
        # The same rule the blog runs under. A bio is published copy.
        from . import ai

        for value, field in ((self.bio, "bio"), (self.credentials, "credentials")):
            if not value:
                continue
            review = ai.review_flags(value)
            if not review.ok:
                raise ValidationError(
                    {field: " ".join(f"{f.why} — “{f.excerpt}”" for f in review.flags)}
                )

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.user.get_full_name() or self.user.email.split("@")[0]
        if not self.slug:
            base = slugify(self.display_name)[:130] or "author"
            candidate, suffix = base, 2
            while type(self).objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def same_as(self) -> list[str]:
        """External profiles, for `Person.sameAs` in JSON-LD."""
        return [url for url in (self.website, self.linkedin_url, self.x_url) if url]

    @property
    def live_post_count(self) -> int:
        from .models import Post

        return Post.objects.live().filter(author=self.user).count()

    @property
    def has_public_page(self) -> bool:
        """An author page needs consent and something to show."""
        return self.is_public and self.live_post_count > 0
