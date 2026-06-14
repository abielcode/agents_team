"""
django.py — Django platform context pack.
Python / DRF / ViewSets / Serializers / ORM / pytest-django / factory_boy / flake8 / mypy
"""

from .base import PlatformContext, VerifierTools


class DjangoPlatform(PlatformContext):
    name = "django"

    def system_prompt_context(self) -> str:
        return """
PLATFORM: Django
LANGUAGE: Python 3.11+
FRAMEWORK: Django 4.2+ with Django REST Framework (DRF)
ARCHITECTURE: DRF ViewSets + Serializers + Service layer
  - Views: DRF ViewSets (ModelViewSet / GenericAPIView as appropriate)
  - Serializers: explicit field declarations — NEVER use fields = '__all__'
  - Services: plain Python classes, zero Django ORM imports (use repositories)
  - Repositories: thin layer wrapping ORM queries, injected into services
  - Models: explicit field definitions, Meta class, __str__ on every model
API FORMAT: JSON, versioned under /api/v1/
AUTHENTICATION: djangorestframework-simplejwt (JWT Bearer tokens)
PERMISSIONS: explicit permission_classes on every ViewSet — never rely on defaults
PAGINATION: PageNumberPagination, set globally in DEFAULT_PAGINATION_CLASS
FILTERING: django-filter with DjangoFilterBackend
LINTERS:
  - flake8: max-line-length=88, ignore=E203,W503
  - black: formatter (must pass --check)
  - mypy: strict mode, type hints required on all public functions
BUILD/CHECK: python manage.py check --deploy (in prod), manage.py check (in dev)
TEST FRAMEWORK:
  - pytest-django (NEVER use unittest.TestCase)
  - @pytest.mark.django_db on all DB tests
  - factory_boy for model factories (class Meta: model = MyModel)
  - DRF APIClient for endpoint tests
  - pytest-mock (mocker fixture) for mocking
CODE CONVENTIONS:
  - Type hints on ALL function signatures including private helpers
  - No bare except — always catch specific exceptions
  - select_related / prefetch_related to avoid N+1 — enforce in services
  - No business logic in serializers (only field validation and transformation)
  - No business logic in views (delegate to service layer)
  - Settings split: config/settings/base.py, dev.py, prod.py, test.py
  - Environment variables via django-environ (.env file)
  - Celery tasks in tasks.py per app
  - Admin registered for every model
FILE STRUCTURE:
  project/
  ├── config/
  │   ├── settings/base.py, dev.py, prod.py, test.py
  │   ├── urls.py
  │   └── wsgi.py
  ├── apps/
  │   └── feature/
  │       ├── models.py
  │       ├── serializers.py
  │       ├── views.py          # ViewSets only
  │       ├── urls.py
  │       ├── services.py       # Business logic
  │       ├── repositories.py   # ORM queries
  │       ├── admin.py
  │       ├── factories.py      # factory_boy
  │       └── tests/
  │           ├── test_models.py
  │           ├── test_services.py
  │           └── test_views.py
  └── manage.py
""".strip()

    def verifier_tools(self) -> VerifierTools:
        return VerifierTools(
            build_cmd="python manage.py check 2>&1",
            test_cmd="pytest --tb=short -q --no-header 2>&1",
            lint_cmd="flake8 . && black --check . && mypy . 2>&1",
            lint_fix_cmd="black . && isort . 2>&1",
        )

    def test_framework_description(self) -> str:
        return (
            "pytest-django for ALL tests — use @pytest.mark.django_db decorator on any test touching the DB. "
            "factory_boy for model factories (class Meta: model = MyModel, factory.Faker for fields). "
            "DRF APIClient: client = APIClient(); client.force_authenticate(user=user); client.get('/api/v1/.../'). "
            "pytest-mock mocker fixture for mocking (mocker.patch('module.Class.method')). "
            "NEVER use unittest.TestCase — pure pytest functions only. "
            "Fixtures in conftest.py at app or project level."
        )
