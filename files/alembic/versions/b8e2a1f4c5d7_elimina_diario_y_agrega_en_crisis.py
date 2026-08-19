"""elimina diario y agrega en_crisis a usuarios

Revision ID: b8e2a1f4c5d7
Revises: 07e9db670b45
Create Date: 2026-08-17

El diario se elimina por decisión del cliente. La señal de crisis
(alerta_crisis del diario) se reemplaza por una bandera persistente
en_crisis en la tabla usuarios. Migración reversible: downgrade()
recrea la tabla entradas_diario y elimina la columna en_crisis.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e2a1f4c5d7'
down_revision: Union[str, None] = '07e9db670b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Señal de crisis persistente (reemplaza alerta_crisis del diario)
    op.add_column(
        'usuarios',
        sa.Column('en_crisis', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f('ix_usuarios_en_crisis'), 'usuarios', ['en_crisis'])

    # El diario se elimina — DROP reversible vía downgrade()
    op.drop_table('entradas_diario')


def downgrade() -> None:
    # Recrear entradas_diario (estructura; los datos no se recuperan tras un DROP)
    op.create_table(
        'entradas_diario',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('usuario_id', sa.String(length=36), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('estado_animo', sa.String(length=10), nullable=True),
        sa.Column('etiquetas', sa.JSON(), nullable=True),
        sa.Column('compartida', sa.Boolean(), nullable=True),
        sa.Column('psicologo_id', sa.String(length=36), nullable=True),
        sa.Column('analisis_ia', sa.JSON(), nullable=True),
        sa.Column('alerta_crisis', sa.Boolean(), nullable=True),
        sa.Column('creada_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('actualizada_en', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['psicologo_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_diario_usuario', 'entradas_diario', ['usuario_id'])
    op.create_index('ix_diario_compartida', 'entradas_diario', ['compartida'])
    op.create_index('ix_diario_alerta', 'entradas_diario', ['alerta_crisis'])

    op.drop_index(op.f('ix_usuarios_en_crisis'), table_name='usuarios')
    op.drop_column('usuarios', 'en_crisis')
