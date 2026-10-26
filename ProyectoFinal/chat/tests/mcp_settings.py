import os

from SpendingAdmin.settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ["SPENDING_MCP_TEST_DB"],
    }
}
