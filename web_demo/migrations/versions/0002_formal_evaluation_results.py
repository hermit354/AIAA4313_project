"""store immutable formal evaluation results per run

Revision ID: 0002_formal_evaluation_results
Revises: 0001_local_demo_schema
"""

from alembic import op

revision = "0002_formal_evaluation_results"
down_revision = "0001_local_demo_schema"
branch_labels = None
depends_on = None

RUN_COLUMNS = [
    ("core_score", "real"),
    ("bonus", "real"),
    ("deduction", "real"),
    ("categories_json", "text"),
    ("evidence_json", "text"),
    ("resume_json", "text"),
    ("github_json", "text"),
    ("evaluation_engine", "text"),
    ("prompt_version", "text"),
    ("schema_mode", "text"),
    ("artifact_path", "text"),
]


def upgrade():
    for name, sql_type in RUN_COLUMNS:
        try:
            op.execute(f"alter table evaluation_runs add column {name} {sql_type}")
        except Exception as exc:
            if "duplicate column" not in str(exc).lower():
                raise


def downgrade():
    # SQLite cannot safely drop these columns on all supported versions.
    pass
