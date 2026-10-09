"""Bind new sessions to a server-selected shift; legacy sessions require login."""
from alembic import op
import sqlalchemy as sa

revision = "0002_session_shift"
down_revision = "0001_f1_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("session_tokens", sa.Column("shift_occurrence_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_session_shift", "session_tokens", "shifts", ["shift_occurrence_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_session_shift", "session_tokens", type_="foreignkey")
    op.drop_column("session_tokens", "shift_occurrence_id")
