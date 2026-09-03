"""split vitals monthly spend into food, transportation, other categories

Revision ID: 87a2aedc338f
Revises: 611273bf187f
Create Date: 2026-09-02 21:56:09.965269

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '87a2aedc338f'
down_revision: Union[str, Sequence[str], None] = '611273bf187f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('financial_vitals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('food_monthly_cents', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('transportation_monthly_cents', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('other_spend_monthly_cents', sa.Integer(), nullable=False, server_default='0'))

    # Preserve any existing estimate rows: fold the old lump total into
    # "other" so a pre-existing user's estimated Profile doesn't silently
    # drop to $0 spend after this migration.
    op.execute("UPDATE financial_vitals SET other_spend_monthly_cents = monthly_spend_estimate_cents")

    with op.batch_alter_table('financial_vitals', schema=None) as batch_op:
        batch_op.drop_column('monthly_spend_estimate_cents')

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('financial_vitals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('monthly_spend_estimate_cents', sa.INTEGER(), nullable=False, server_default='0'))

    op.execute(
        "UPDATE financial_vitals SET monthly_spend_estimate_cents = "
        "food_monthly_cents + transportation_monthly_cents + other_spend_monthly_cents"
    )

    with op.batch_alter_table('financial_vitals', schema=None) as batch_op:
        batch_op.drop_column('other_spend_monthly_cents')
        batch_op.drop_column('transportation_monthly_cents')
        batch_op.drop_column('food_monthly_cents')

    # ### end Alembic commands ###
