"""One immutable approval decision per Action revision; reuse F1's existing tables."""
from alembic import op

revision = "0003_action_approval_unique"
down_revision = "0002_session_shift"
branch_labels = None
depends_on = None


def upgrade():
    # Existing duplicates must fail visibly; never discard historical approvals.
    op.create_unique_constraint("uq_approvals_action_revision", "approvals", ["action_id", "action_revision"])


def downgrade():
    op.drop_constraint("uq_approvals_action_revision", "approvals", type_="unique")
