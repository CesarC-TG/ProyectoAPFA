"""crea cola_atencion y auditoria_acceso

Revision ID: d3f7c9e2a1b4
Revises: b8e2a1f4c5d7
Create Date: 2026-08-17

Cola de trabajo de psicólogos (estado: pendiente/tomada/resuelta) y log
inmutable de accesos a expedientes y acciones sobre la cola.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3f7c9e2a1b4'
down_revision: Union[str, None] = 'b8e2a1f4c5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cola_atencion',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('estudiante_id', sa.String(length=36), nullable=False),
        sa.Column('psicologo_id', sa.String(length=36), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False),
        sa.Column('prioridad', sa.String(length=20), nullable=False),
        sa.Column('origen', sa.String(length=30), nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('creada_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('tomada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resuelta_en', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['estudiante_id'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['psicologo_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cola_estado', 'cola_atencion', ['estado'])
    op.create_index('ix_cola_prioridad', 'cola_atencion', ['prioridad'])
    op.create_index('ix_cola_estudiante', 'cola_atencion', ['estudiante_id'])
    op.create_index('ix_cola_psicologo', 'cola_atencion', ['psicologo_id'])

    op.create_table(
        'auditoria_acceso',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('psicologo_id', sa.String(length=36), nullable=True),
        sa.Column('estudiante_id', sa.String(length=36), nullable=True),
        sa.Column('accion', sa.String(length=40), nullable=False),
        sa.Column('detalle', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['estudiante_id'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['psicologo_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auditoria_psicologo', 'auditoria_acceso', ['psicologo_id'])
    op.create_index('ix_auditoria_estudiante', 'auditoria_acceso', ['estudiante_id'])
    op.create_index('ix_auditoria_accion', 'auditoria_acceso', ['accion'])


def downgrade() -> None:
    op.drop_index('ix_auditoria_accion', table_name='auditoria_acceso')
    op.drop_index('ix_auditoria_estudiante', table_name='auditoria_acceso')
    op.drop_index('ix_auditoria_psicologo', table_name='auditoria_acceso')
    op.drop_table('auditoria_acceso')

    op.drop_index('ix_cola_psicologo', table_name='cola_atencion')
    op.drop_index('ix_cola_estudiante', table_name='cola_atencion')
    op.drop_index('ix_cola_prioridad', table_name='cola_atencion')
    op.drop_index('ix_cola_estado', table_name='cola_atencion')
    op.drop_table('cola_atencion')
