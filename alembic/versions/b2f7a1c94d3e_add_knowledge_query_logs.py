"""add knowledge query logs

Revision ID: b2f7a1c94d3e
Revises: 68e6dbc3518b
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f7a1c94d3e'
down_revision: Union[str, Sequence[str], None] = '68e6dbc3518b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('knowledge_query_logs',
    sa.Column('user_id', sa.String(length=64), nullable=False, comment='用户 ID'),
    sa.Column('role', sa.String(length=32), nullable=False, comment='用户角色'),
    sa.Column('question', sa.String(length=1000), nullable=False, comment='用户提问'),
    sa.Column('intent', sa.String(length=50), nullable=False, comment='检索意图'),
    sa.Column('channels', sa.String(length=100), nullable=False, comment='使用的检索通道'),
    sa.Column('answer_preview', sa.String(length=500), nullable=False, comment='回答预览'),
    sa.Column('duration_ms', sa.Integer(), nullable=False, comment='检索耗时(ms)'),
    sa.Column('is_grounded', sa.Boolean(), nullable=True, comment='幻觉检测是否有据'),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_query_logs_intent', 'knowledge_query_logs', ['intent'], unique=False)
    op.create_index('ix_knowledge_query_logs_user', 'knowledge_query_logs', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_knowledge_query_logs_user', table_name='knowledge_query_logs')
    op.drop_index('ix_knowledge_query_logs_intent', table_name='knowledge_query_logs')
    op.drop_table('knowledge_query_logs')
