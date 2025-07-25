"""create flight_bookings and flight_legs tables

Revision ID: a6d611cfa283
Revises: a1ed452e9bf4
Create Date: 2025-07-26 13:18:39.398289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6d611cfa283'
down_revision: Union[str, Sequence[str], None] = 'a1ed452e9bf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('flight_bookings',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('thread_id', sa.String(), nullable=False),
    sa.Column('booking_reference', sa.String(), nullable=False),
    sa.Column('full_name', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=False),
    sa.Column('airline', sa.String(), nullable=False),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('currency', sa.String(), nullable=True),
    sa.Column('booking_link', sa.String(), nullable=True),
    sa.Column('is_multi_city', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('flight_legs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('booking_id', sa.String(), nullable=True),
    sa.Column('departure_time', sa.String(), nullable=True),
    sa.Column('arrival_time', sa.String(), nullable=True),
    sa.Column('origin', sa.String(), nullable=True),
    sa.Column('destination', sa.String(), nullable=True),
    sa.Column('duration', sa.String(), nullable=True),
    sa.Column('stops', sa.Integer(), nullable=True),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['booking_id'], ['flight_bookings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('flight_legs')
    op.drop_table('flight_bookings')
    # ### end Alembic commands ###
