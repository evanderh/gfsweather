"""init

Revision ID: 6fe778ff2c89
Revises: 
Create Date: 2024-06-10 18:32:33.031724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fe778ff2c89'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('forecast_cycles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('datetime', sa.DateTime(), nullable=False),
    sa.Column('is_complete', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('datetime')
    )
    op.create_table('forecast_hours',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hour', sa.Integer(), nullable=False),
    sa.Column('cycle_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['cycle_id'], ['forecast_cycles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_forecast_hours_cycle_id'), 'forecast_hours', ['cycle_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_forecast_hours_cycle_id'), table_name='forecast_hours')
    op.drop_table('forecast_hours')
    op.drop_table('forecast_cycles')
    # ### end Alembic commands ###
