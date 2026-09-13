"""Seed the blog with its starting categories and three real articles.

Not lorem ipsum, and not AI-generated: these are the three questions the agency
answers most often, written out properly. A blog that launches with placeholder
posts is worse than one that launches with three good ones, and an empty /blog
in a demo tells a prospective client nothing.

Every article here obeys the house style in apps/blog/ai.py — no country, no
school, no unverified figure, admission before visa — and the command asserts
that before it writes anything. If someone later edits the prose in this file and
breaks a rule, the seed fails loudly rather than putting a claim on the site.

Idempotent: run it as often as you like. Existing posts are left alone.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.blog import ai
from apps.blog.models import AuthorProfile, BlogSettings, Category, Post, PostFaq, Tag

CATEGORIES = [
    (
        "Applying",
        "applying",
        "How an application actually works, step by step, and what each step needs from you.",
        10,
    ),
    (
        "Documents",
        "documents",
        "Transcripts, translations, references, passports — what to get, and in what order.",
        20,
    ),
    (
        "Money",
        "money",
        "What studying abroad costs when nobody is rounding the numbers down for you.",
        30,
    ),
    (
        "Visas",
        "visas",
        "What happens after an admission letter, and what no agent can promise you.",
        40,
    ),
]

TAGS = [
    "documents",
    "transcripts",
    "motivation letter",
    "proof of funds",
    "tuition-free",
    "timeline",
    "scams",
]


POSTS = [
    {
        "title": "Start with your transcript, not with the applications",
        "category": "documents",
        "tags": ["documents", "transcripts", "timeline"],
        "excerpt": (
            "Almost everyone starts by looking at schools. The people who get in on time start "
            "by requesting their transcript, because it is the one document they do not control."
        ),
        "focus_keyword": "how to get your transcript for a foreign application",
        "faqs": [
            (
                "How long does a transcript take?",
                "It varies enormously by institution, and nobody can promise you a date. That is "
                "exactly why you request it first rather than last.",
            ),
            (
                "Is a statement of result the same as a transcript?",
                "No. A statement of result says what you scored; an official transcript is the "
                "full record, issued and sealed by the institution. Most applications want the "
                "second one.",
            ),
        ],
        "meta_title": "Get your transcript first, then apply",
        "meta_description": (
            "The transcript is the slowest document in any international application and the one "
            "you cannot rush. Here is how to start it before you start applying."
        ),
        "body": """
Request your transcript before you look at a single school. It is the one
document in your application that somebody else has to produce, on their
schedule, and it is the reason most applications miss an intake.

Everything else in the file you can produce in an afternoon if you have to. A
motivation letter is you at a keyboard. A CV is you at a keyboard. A passport
renewal has a queue but it has a published one. A transcript depends on a
records office answering a request, and the honest answer about how long that
takes is: it varies enormously, and nobody can promise you a date.

## What you are actually asking for

Two different things get called a transcript, and asking for the wrong one
costs you a second request.

A **statement of result** says what you scored. It is usually what a school
gives a graduate first, and for most applications it is not enough on its own.

An **official transcript** is the full academic record, issued and sealed by the
institution, usually sent directly to whoever is receiving it rather than handed
to you. This is what an application normally means. Some institutions will only
release it to another institution, which means you need somewhere for it to go
before you can order it — and that, not the fee, is what catches people out.

Ask the records office which of the two they issue, whether they will release it
to you or only to a receiving institution, and what they charge. Get that in
writing if you can, even if it is only a WhatsApp reply.

## Why this document sets your whole timeline

Work backwards from an intake and the transcript is the first thing on the
calendar, not the last.

An application closes on a date. Your documents have to be complete before that
date, not started. If a translation is needed, the translator needs the finished
transcript in hand, which means the transcript has to be done before the
translation is done. And if your institution only sends transcripts directly to
a receiving school, then you need to have chosen the school before the
transcript can even be ordered.

That chain is why "I will sort the paperwork once I know where I am applying" is
the single most expensive sentence in this process. The paperwork decides which
intakes are still open to you.

## What to do this week

Call or visit the records office of every institution you attended after
secondary school. For each one, write down: what they issue, who they will
release it to, what it costs, and what they need from you to start.

Then request it. Not when you have a shortlist. Now. A transcript sitting in a
drawer costs you nothing; a transcript you have not requested can cost you a
whole intake.

## Where we come in

Finding out what each school requires, and in what form, is the part we do
first — because the list of requirements is what tells you which documents to
start on and which intakes are realistic. We tell you the whole list before you
spend anything on a translation or a test, so nothing in your file turns out to
have been unnecessary.
""".strip(),
    },
    {
        "title": "Tuition-free is not the same as free",
        "category": "money",
        "tags": ["tuition-free", "proof of funds"],
        "excerpt": (
            "A tuition-free place means the school does not charge you to teach you. Everything "
            "else about the year still costs money, and the part that stops most applications is "
            "money you never actually spend."
        ),
        "focus_keyword": "is tuition-free study really free",
        "faqs": [
            (
                "If tuition is free, what do I actually pay for?",
                "Somewhere to live, food, travel, insurance where it is required, document "
                "translation, and a language test where the course needs one. Those vary by "
                "school and by city and they change, so ask us for the current figures.",
            ),
            (
                "What is proof of funds?",
                "Showing that money exists in an account, often for some minimum period before "
                "you apply. You are not asked to spend it. Money deposited days before a decision "
                "can fail the requirement even when the amount is right.",
            ),
        ],
        "meta_title": "Tuition-free is not the same as free",
        "meta_description": (
            "What a tuition-free place does and does not cover, and why the requirement that stops "
            "most applications is money you are never asked to spend."
        ),
        "body": """
Tuition-free means one specific thing: the school does not charge you a fee to
teach you. It does not mean the year is free, and budgeting as though it does is
how people come unstuck a few weeks before an intake.

## What the place does cover

The teaching. Usually the examinations. Often access to the library, the labs and
whatever student services the institution runs. That is a genuinely enormous
saving and it is the whole reason this route is worth pursuing — but it is a
saving on one line of the budget, not on the budget.

## What is still yours to pay

Somewhere to live, and food. Getting there. Insurance, where it is required.
Registration or administrative charges, which are not tuition and are usually
small but are rarely zero. Getting your documents translated and, sometimes,
formally evaluated. A language test, where the course actually requires one.

Every one of those varies by school and by city, and every one of them changes
from year to year. Anyone quoting you a single confident figure for "the cost of
studying abroad" is quoting you a number they made up or a number that was true
somewhere, once. Ask us for the figures that apply to the specific schools on
your list, and ask again if months pass.

## The requirement that actually stops people

Here is the part that surprises almost everyone: the biggest financial hurdle is
usually money you never spend.

Before you are given permission to enter a country to study, you generally have
to demonstrate that you can support yourself while you are there. Not spend it
— demonstrate it. That normally means showing that a certain amount of money
exists, in an account, and in many cases that it has been sitting there for some
minimum period rather than arriving the week before you applied.

Read that last part twice, because it is the detail that ends applications.
Money borrowed and deposited a few days before a decision can fail the
requirement even though the amount is right. The money has to have a history.

So if this route is your plan, the account matters as much as the application,
and it matters months earlier. That is a conversation to have with whoever in
your family is supporting you now, not after you hold an offer.

## What this means for how you plan

Plan the year, not the tuition. Write down what you will need for somewhere to
live, food, travel, insurance and documents, then find out what has to be shown
before you go and how long it has to have been there. If those two numbers are
reachable, tuition-free study is genuinely within reach and the saving is
enormous. If they are not yet, you now know exactly what you are working
towards, which is a far better position than finding out in the final week.

We go through both sets of figures with you against the specific schools on your
list, because they are the numbers that decide whether an offer turns into a
departure.
""".strip(),
    },
    {
        "title": "Admission comes first. Anyone who tells you otherwise is guessing",
        "category": "visas",
        "tags": ["timeline", "scams"],
        "excerpt": (
            "A study visa is an application to go and study at a named school. Without the "
            "admission letter there is nothing to apply about — and starting at the wrong end is "
            "the most common way people lose money."
        ),
        "focus_keyword": "does admission come before the visa",
        "faqs": [
            (
                "Can I start the visa before I have an admission letter?",
                "No. A study visa is an application to go and study a named course at a named "
                "institution that has agreed to take you. Without the letter there is nothing to "
                "apply about.",
            ),
            (
                "What should make me walk away from an agent?",
                "An offer to start the visa before you hold an admission letter, a promised "
                "outcome of any kind, or a large fee for a school they will name later with no "
                "written list of what it requires.",
            ),
        ],
        "style_override_reason": (
            "This article exists to teach readers to recognise the exact phrases a dishonest "
            "agent uses — “guaranteed visa”, “guaranteed admission”, "
            "starting a visa before an admission letter. It quotes them in order to warn against "
            "them, and every one appears inside a sentence telling the reader to walk away."
        ),
        "meta_title": "Admission comes before the visa",
        "meta_description": (
            "Why an admission letter has to exist before a study visa application means anything, "
            "and what that tells you about anyone offering to reverse the order."
        ),
        "body": """
The order is: admission first, then the visa. It is not a preference or a
strategy, it is what a study visa is. You are asking permission to enter a
country in order to study a named course at a named institution that has agreed
to take you. Remove the admission letter and there is no application to make.

This matters more than it sounds, because reversing the order is one of the most
reliable ways to lose money in this process.

## What the sequence actually looks like

You work out which schools will take your qualifications and teach the subject
you want. You find out precisely what each one requires. You assemble the file —
transcript, translations, CV, motivation letter, whatever else is on the list —
and you apply. You wait. The school decides.

If the answer is yes, you receive an admission letter. Only then does the visa
application begin, and it begins as a file built around that letter: proof of
funds, health checks, insurance, accommodation, an appointment.

Every step there depends on the one before it. There is no version where the
last step happens first.

## Why people get sold the reverse

Because "we will get you the visa" sounds like the hard part being taken care
of, and "we will help you assemble a strong application" sounds like work you
still have to do. One of those is a promise nobody can keep. The other is the
actual job.

Watch for these three, and treat any of them as a reason to walk away:

- An offer to start the visa process before you hold an admission letter.
- A guaranteed visa, or a guaranteed admission. The school decides the first and
  the embassy decides the second. Nobody else has a vote, and anyone claiming
  otherwise is either confused or selling you something else.
- A large fee now for a school named later, with no written list of what that
  school requires.

## What you should be able to check at every stage

You should know which schools you are applying to and why each one is on the
list. You should have every requirement in writing before you spend money on
meeting it. You should see your own documents and your own application. You
should be told what is waiting on you and what is waiting on somebody else.

An agent who wants you out of the process is usually hiding how little of it
there is. The work is real, but it is not secret, and none of it requires you to
take anything on faith.

## Where we come in

We do the four things that actually move an application: find the schools, give
you the full requirement list in writing, write the CV and the motivation letter
with you, and — once an admission letter exists — prepare the visa file with you
and stay with it to the decision. In that order, because there is no other
order.
""".strip(),
    },
]


class Command(BaseCommand):
    help = "Create the blog's starting categories, tags and three launch articles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--author",
            default="",
            help="Email of the staff user to credit and record as publisher. Defaults to the first superadmin.",
        )
        parser.add_argument(
            "--draft",
            action="store_true",
            help="Create the posts as drafts instead of publishing them.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        author = self._resolve_author(options["author"])

        # Fail before writing anything if the prose in this file has drifted out
        # of house style — a seed that quietly publishes a banned claim would be
        # the worst possible place for one. A post that deliberately quotes the
        # claims it warns against carries a written reason - the same escape
        # hatch the composer offers - and is exempt.
        for post in POSTS:
            if post.get("style_override_reason"):
                continue
            review = ai.review_flags(post["body"])
            if not review.ok:
                raise CommandError(
                    f"“{post['title']}” breaks the house style:\n"
                    + "\n".join(f"  - {flag.why} → {flag.excerpt}" for flag in review.flags)
                )

        self._ensure_settings()
        self._ensure_author_profile(author)

        categories = {}
        for name, slug, description, order in CATEGORIES:
            category, created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": description, "display_order": order},
            )
            categories[slug] = category
            if created:
                self.stdout.write(f"  category  {name}")

        tags = {}
        for name in TAGS:
            tag, created = Tag.objects.get_or_create(name=name)
            tags[name] = tag
            if created:
                self.stdout.write(f"  tag       {name}")

        written = 0
        for spec in POSTS:
            if Post.objects.filter(title=spec["title"]).exists():
                self.stdout.write(f"  skipped   {spec['title']} (already exists)")
                continue

            post = Post(
                title=spec["title"],
                excerpt=spec["excerpt"],
                body=spec["body"],
                category=categories[spec["category"]],
                author=author,
                focus_keyword=spec["focus_keyword"],
                meta_title=spec["meta_title"],
                meta_description=spec["meta_description"],
                ai_involvement=Post.AiInvolvement.NONE,
                style_override_reason=spec.get("style_override_reason", ""),
            )
            if not options["draft"]:
                post.status = Post.Status.PUBLISHED
                post.published_by = author
                post.published_at = timezone.now()
            post.save()
            post.tags.set([tags[name] for name in spec["tags"]])
            for order, (question, answer) in enumerate(spec.get("faqs", []), start=1):
                PostFaq.objects.create(
                    post=post, question=question, answer=answer, display_order=order * 10
                )
            written += 1
            self.stdout.write(f"  post      {post.slug}")

        state = "drafted" if options["draft"] else "published"
        self.stdout.write(
            self.style.SUCCESS(
                f"{written} post(s) {state}, {len(CATEGORIES)} categories, {len(TAGS)} tags, "
                f"{PostFaq.objects.count()} FAQ entries."
            )
        )

    def _ensure_settings(self) -> None:
        """Touch the settings singleton so it exists with its defaults.

        Not overwritten if it is already there — someone may have tuned it, and a
        seed command that silently resets the site's configuration is a trap.
        """
        existed = BlogSettings.objects.exists()
        BlogSettings.load()
        self.stdout.write("  settings  " + ("already configured" if existed else "created with defaults"))

    def _ensure_author_profile(self, author: User) -> None:
        """Give the seeded author a real byline.

        Without a profile the articles ship with an account name and no `Person`
        markup, which is most of the point of having authored articles at all.
        """
        profile, created = AuthorProfile.objects.get_or_create(
            user=author,
            defaults={
                "display_name": author.get_full_name() or "Nasuru",
                "headline": "International education agent",
                "bio": (
                    "We sit with applicants through the whole process — finding schools that will "
                    "take their qualifications, writing the motivation letter with them, and "
                    "preparing the visa file once an admission letter exists."
                ),
                "is_public": True,
            },
        )
        if created:
            self.stdout.write(f"  author    {profile.slug}")

    def _resolve_author(self, email: str) -> User:
        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist as exc:
                raise CommandError(f"No user with the email {email}.") from exc

        author = User.objects.filter(role=User.Role.SUPERADMIN).order_by("created_at").first()
        if author is None:
            raise CommandError(
                "No superadmin to credit. Create one with `make superuser`, or pass --author."
            )
        return author
