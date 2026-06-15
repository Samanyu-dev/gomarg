"""add metadata payload to email events

Revision ID: add_email_metadata
Revises: add_lead_score_cols
Create Date: 2026-06-15 12:00:30.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_email_metadata'
down_revision = 'add_lead_score_cols'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('email_events', sa.Column('metadata_payload', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('email_events', 'metadata_payload')
