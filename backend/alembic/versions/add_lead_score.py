"""add lead score and sequence columns

Revision ID: add_lead_score_cols
Revises: d50c47228c21
Create Date: 2026-06-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_lead_score_cols'
down_revision = 'd50c47228c21'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('leads', sa.Column('lead_score', sa.String(), server_default='cold', nullable=True))
    op.add_column('leads', sa.Column('sequence_step', sa.Integer(), server_default='0', nullable=True))
    op.add_column('leads', sa.Column('next_contact_at', sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column('leads', 'next_contact_at')
    op.drop_column('leads', 'sequence_step')
    op.drop_column('leads', 'lead_score')
