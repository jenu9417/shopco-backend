"""Import every module's models here so Alembic autogenerate and tests see all tables."""

from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
