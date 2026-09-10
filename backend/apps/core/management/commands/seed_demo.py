"""
Seed the platform with realistic starting data.

The HWR Berlin requirement set is transcribed from the agency's own
spreadsheet tracker, so the digital checklist can be compared line for line
against the thing it replaces.

    python manage.py seed_demo
    python manage.py seed_demo --with-student   # also create a demo student + application
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import StudentProfile
from apps.applications.services import generate_checklist
from apps.forms_engine.models import FormDefinition
from apps.referrals.models import ReferralRewardRule
from apps.schools.models import (
    Country,
    Programme,
    RequirementCategory,
    RequirementItem,
    School,
    SchoolRequirementSet,
)

User = get_user_model()

CATEGORIES = [
    ("Documents & Transcripts", 10, "Academic records, certificates and identity documents."),
    ("English Proof", 20, "IELTS, TOEFL or an accepted equivalent."),
    ("Language (Other)", 30, "German, French or another language of instruction."),
    ("Application Forms", 40, "Portal accounts, uni-assist and school application forms."),
    ("Financial", 50, "Proof of funds, blocked accounts, sponsorship letters."),
    ("Visa & Relocation", 60, "Visa file, insurance, accommodation, travel."),
    ("Spouse / Family", 70, "Dependant and family reunification documents."),
]

# (category, label, required, priority, evidence, shareable_key, help_text)
HWR_REQUIREMENTS = [
    ("Documents & Transcripts", "International passport (bio-data page)", True, "high", "document", "passport", "Must be valid for at least 12 months beyond intake."),
    ("Documents & Transcripts", "WAEC/NECO certificate and results", True, "high", "document", "waec", "Scanned original, plus the online result printout."),
    ("Documents & Transcripts", "University transcript", True, "high", "document", "", "Official transcript covering all completed semesters."),
    ("Documents & Transcripts", "University admission letter", False, "medium", "document", "", "Where available — helps uni-assist evaluate the entrance route."),
    ("Documents & Transcripts", "Prior certificate / academic record", False, "medium", "document", "", "Any additional completed programme (e.g. pathway or diploma)."),
    ("Documents & Transcripts", "CV / resume", True, "medium", "document", "cv", "One or two pages, reverse-chronological."),
    ("Documents & Transcripts", "Certified translations", False, "medium", "document", "", "Required for any document not already in English or German."),
    ("English Proof", "Confirm the school's exact English evidence policy", True, "high", "task", "", "Policies differ — confirm in writing before booking a test."),
    ("English Proof", "IELTS / TOEFL result", True, "high", "document_and_form", "english_test", "Target IELTS 6.0–6.5 overall. Valid for 24 months."),
    ("Language (Other)", "German A2 certificate (minimum)", True, "high", "document", "german_a2", "A2 is the admission minimum; B1 is recommended before travel."),
    ("Language (Other)", "German B1 certificate", False, "low", "document", "german_b1", "Stretch goal — strengthens both the application and the visa file."),
    ("Application Forms", "uni-assist account created", True, "high", "task", "", "Register before the application window opens."),
    ("Application Forms", "uni-assist entries completed", True, "high", "task", "", "Every prior institution entered with its own transcript."),
    ("Application Forms", "Motivation letter", True, "medium", "document", "", "One page, specific to this programme."),
    ("Application Forms", "Application submitted", True, "high", "task", "", "Submit early in the window rather than at the deadline."),
    ("Financial", "Proof of financial resources (blocked account)", True, "high", "document_and_form", "blocked_account", "Blocked account confirmation covering one year of living costs."),
    ("Visa & Relocation", "Admission letter from the school", True, "high", "document", "", "Issued after acceptance; the visa file cannot start without it."),
    ("Visa & Relocation", "Health insurance confirmation", True, "medium", "document", "health_insurance", "Statutory or recognised private cover."),
    ("Visa & Relocation", "Accommodation confirmation", True, "medium", "document", "", "Registered address or confirmed tenancy."),
    ("Visa & Relocation", "Student visa application submitted", True, "high", "task", "", "Book the appointment as soon as the admission letter arrives."),
    ("Spouse / Family", "Marriage certificate", True, "high", "document", "marriage_certificate", "Certified copy plus a translation where needed."),
    ("Spouse / Family", "Spouse's passport and documents", True, "high", "document", "", "For the dependant / family reunification application."),
]

INTAKE_FORM_SCHEMA = {
    "sections": [
        {
            "key": "personal",
            "title": "About you",
            "description": "This is the profile your counsellor works from.",
            "fields": [
                {"key": "full_name", "type": "text", "label": "Full name (as on your passport)", "required": True},
                {"key": "date_of_birth", "type": "date", "label": "Date of birth", "required": True},
                {"key": "phone", "type": "phone", "label": "Phone number", "required": True},
                {"key": "whatsapp", "type": "phone", "label": "WhatsApp number", "required": False,
                 "help_text": "If different from the number above."},
                {"key": "state_of_residence", "type": "text", "label": "State of residence", "required": True},
                {"key": "marital_status", "type": "select", "label": "Marital status", "required": True,
                 "options": [
                     {"value": "single", "label": "Single"},
                     {"value": "married", "label": "Married"},
                 ]},
                # The conditional case from plan §3.2, made real.
                {"key": "spouse_travelling", "type": "checkbox", "label": "My spouse will travel with me",
                 "required": False,
                 "visible_when": {"all": [{"field": "marital_status", "op": "eq", "value": "married"}]}},
            ],
        },
        {
            "key": "education",
            "title": "Education",
            "fields": [
                {"key": "highest_qualification", "type": "select", "label": "Highest qualification completed",
                 "required": True,
                 "options": [
                     {"value": "secondary", "label": "Secondary school (WAEC/NECO)"},
                     {"value": "diploma", "label": "Diploma / OND"},
                     {"value": "bachelors", "label": "Bachelor's degree"},
                     {"value": "masters", "label": "Master's degree"},
                 ]},
                {"key": "institution", "type": "text", "label": "Institution attended", "required": True},
                {"key": "graduation_year", "type": "number", "label": "Year completed", "required": False,
                 "validation": {"min": 1970, "max": 2035}},
                {"key": "cgpa", "type": "text", "label": "CGPA / grade", "required": False},
                {"key": "has_english_test", "type": "select", "label": "Do you have an English test result?",
                 "required": True,
                 "options": [
                     {"value": "yes", "label": "Yes"},
                     {"value": "booked", "label": "Booked, not yet sat"},
                     {"value": "no", "label": "Not yet"},
                 ]},
                {"key": "english_score", "type": "text", "label": "Overall score", "required": True,
                 "visible_when": {"all": [{"field": "has_english_test", "op": "eq", "value": "yes"}]}},
            ],
        },
        {
            "key": "plans",
            "title": "Your plans",
            "fields": [
                {"key": "target_countries", "type": "multiselect", "label": "Countries you're considering",
                 "required": True,
                 "options": [
                     {"value": "germany", "label": "Germany"},
                     {"value": "uk", "label": "United Kingdom"},
                     {"value": "canada", "label": "Canada"},
                     {"value": "ireland", "label": "Ireland"},
                     {"value": "usa", "label": "United States"},
                 ]},
                {"key": "target_intake", "type": "text", "label": "Target intake", "required": True,
                 "help_text": 'For example "October 2027".'},
                {"key": "funding", "type": "radio", "label": "How will your studies be funded?", "required": True,
                 "options": [
                     {"value": "self", "label": "Self / family"},
                     {"value": "sponsor", "label": "Sponsor"},
                     {"value": "scholarship", "label": "Scholarship (applying)"},
                 ]},
                {"key": "consent", "type": "consent", "label":
                 "I consent to Nasuru processing my documents for the purpose of my applications.",
                 "required": True,
                 "help_text": "You can withdraw consent at any time; see our privacy policy."},
            ],
        },
    ]
}


class Command(BaseCommand):
    help = "Seed requirement categories, the HWR Berlin requirement set, an intake form and referral rules."

    def add_arguments(self, parser):
        parser.add_argument("--with-student", action="store_true", help="Also create a demo student and application.")

    @transaction.atomic
    def handle(self, *args, **options):
        categories = self._categories()
        school, programme = self._school()
        requirement_set = self._requirements(school, programme, categories)
        self._intake_form()
        self._referral_rules()

        if options["with_student"]:
            self._demo_student(school, programme)

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded {len(categories)} categories, {school.name} "
            f"({requirement_set.items.count()} requirements, v{requirement_set.version} published)."
        ))
        self.stdout.write("Next: python manage.py createsuperuser  →  http://localhost:8000/admin/")

    def _categories(self) -> dict:
        result = {}
        for name, order, description in CATEGORIES:
            category, _ = RequirementCategory.objects.update_or_create(
                name=name, defaults={"display_order": order, "description": description}
            )
            result[name] = category
        self.stdout.write(f"  categories: {len(result)}")
        return result

    def _school(self):
        germany, _ = Country.objects.get_or_create(
            iso_code="DE", defaults={"name": "Germany"}
        )
        school, _ = School.objects.update_or_create(
            slug="hwr-berlin",
            defaults={
                "name": "HWR Berlin",
                "kind": School.Kind.UNIVERSITY,
                "country": germany,
                "city": "Berlin",
                "website": "https://www.hwr-berlin.de",
                "description": "Berlin School of Economics and Law.",
                "attributes": {"application_route": "uni-assist", "tuition_free": True},
            },
        )
        programme, _ = Programme.objects.update_or_create(
            school=school,
            slug="international-business-management",
            defaults={
                "name": "International Business Management",
                "level": Programme.Level.UNDERGRADUATE,
                "language_of_instruction": "German & English",
                "intakes": ["October 2027"],
                "tuition_amount": Decimal("0.00"),
                "tuition_currency": "EUR",
                "attributes": {"window": "1 June – 15 July", "german_minimum": "A2"},
            },
        )
        self.stdout.write(f"  school: {school.name} / {programme.name}")
        return school, programme

    def _requirements(self, school, programme, categories) -> SchoolRequirementSet:
        existing = SchoolRequirementSet.objects.filter(
            programme=programme, status=SchoolRequirementSet.Status.PUBLISHED
        ).first()
        if existing:
            self.stdout.write(f"  requirements: already published (v{existing.version}) — left alone")
            return existing

        requirement_set = SchoolRequirementSet.objects.create(
            school=school,
            programme=programme,
            name="HWR Berlin IBM — October 2027 intake",
            notes="Transcribed from the agency's HWR Berlin application tracker.",
        )
        for index, (category, label, required, priority, evidence, key, help_text) in enumerate(HWR_REQUIREMENTS):
            RequirementItem.objects.create(
                requirement_set=requirement_set,
                category=categories[category],
                label=label,
                help_text=help_text,
                is_required=required,
                priority=priority,
                evidence_type=evidence,
                accepted_file_types=[".pdf", ".jpg", ".png"] if evidence != "task" else [],
                is_shareable=bool(key),
                shareable_key=key,
                expires_after_months=24 if key == "english_test" else None,
                display_order=index,
            )
        requirement_set.publish()
        self.stdout.write(f"  requirements: {requirement_set.items.count()} items published as v1")
        return requirement_set

    def _intake_form(self) -> FormDefinition:
        if FormDefinition.objects.filter(slug="student-intake", status=FormDefinition.Status.PUBLISHED).exists():
            self.stdout.write("  intake form: already published — left alone")
            return FormDefinition.live("student-intake")

        form = FormDefinition.objects.create(
            slug="student-intake",
            title="Student intake",
            description="Tell us about yourself so your counsellor can shortlist schools.",
            audience=FormDefinition.Audience.PAID_STUDENT,
            purpose=FormDefinition.Purpose.STUDENT_INTAKE,
            schema=INTAKE_FORM_SCHEMA,
            success_message="Thank you — your counsellor will review this within one working day.",
        )
        form.full_clean()
        form.publish()
        self.stdout.write("  intake form: published v1")
        return form

    def _referral_rules(self):
        rules = [
            {
                "name": "Signup bonus",
                "trigger": ReferralRewardRule.Trigger.SIGNUP,
                "calculation": ReferralRewardRule.Calculation.FIXED,
                "amount": Decimal("0.00"),  # deliberately zero: signups earn nothing (§6.2)
                "is_active": False,
            },
            {
                "name": "Access fee conversion",
                "trigger": ReferralRewardRule.Trigger.PAID,
                "calculation": ReferralRewardRule.Calculation.PERCENTAGE,
                "amount": Decimal("10.00"),
                "max_amount": Decimal("2000.00"),
                "is_active": True,
            },
            {
                "name": "Enrolment bonus",
                "trigger": ReferralRewardRule.Trigger.ENROLLED,
                "calculation": ReferralRewardRule.Calculation.FIXED,
                "amount": Decimal("10000.00"),
                "requires_manual_approval": True,
                "is_active": True,
            },
        ]
        for rule in rules:
            ReferralRewardRule.objects.update_or_create(name=rule["name"], defaults=rule)
        self.stdout.write(f"  referral rules: {len(rules)}")

    def _demo_student(self, school, programme):
        from apps.applications.models import Application

        user, created = User.objects.get_or_create(
            email="demo.student@example.com",
            defaults={"first_name": "Demo", "last_name": "Student", "role": User.Role.STUDENT},
        )
        if created:
            user.set_password("demo-password-1234")
            user.save()
        student = StudentProfile.objects.get(user=user)
        student.has_platform_access = True
        student.stage = StudentProfile.Stage.PAID
        student.save()

        application, _ = Application.objects.get_or_create(
            student=student, school=school, programme=programme, intake="October 2027"
        )
        if not hasattr(application, "checklist"):
            checklist = generate_checklist(application)
            self.stdout.write(
                f"  demo student: demo.student@example.com / demo-password-1234 "
                f"— checklist with {checklist.items.count()} items at {checklist.percent_complete}%"
            )
