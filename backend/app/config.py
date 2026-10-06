"""Runtime configuration.

DATABASE_URL can point at PostgreSQL (postgresql+psycopg2://...) for the
real deployment.  When unset, the app falls back to a local SQLite file so
the whole stack can be exercised without a database server.
"""
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "mcda.db")
    ),
)

# Tight tolerance for "weights must sum to 1" validation.
WEIGHT_SUM_TOLERANCE = 1e-6
