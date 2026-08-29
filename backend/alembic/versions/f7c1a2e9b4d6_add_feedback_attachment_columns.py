"""Add feedback attachment columns

Revision ID: f7c1a2e9b4d6
Revises: 4dabbae10e68
Create Date: 2026-08-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f7c1a2e9b4d6'
down_revision: Union[str, Sequence[str], None] = '4dabbae10e68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attachment', sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column('attachment_filename', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('attachment_content_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.drop_column('attachment_content_type')
        batch_op.drop_column('attachment_filename')
        batch_op.drop_column('attachment')
