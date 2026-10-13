"""Asset registry, asset events, background jobs; chunk sections; "queued" document status.

After upgrading, re-index existing documents (python -m server.app.cli reindex) so they get
per-chunk entities, events and the bge-small embeddings.

Revision ID: 61a439b32fb4
Revises: c3f0af3a60f2
Create Date: 2026-10-13 21:02:55.278705
"""
from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op


revision: str = '61a439b32fb4'
down_revision: str | None = 'c3f0af3a60f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('assets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tag', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), server_default='', nullable=False),
    sa.Column('asset_class', sa.String(length=64), server_default='', nullable=False),
    sa.Column('location', sa.String(length=200), server_default='', nullable=False),
    sa.Column('criticality', sa.String(length=16), server_default='', nullable=False),
    sa.Column('manufacturer', sa.String(length=128), server_default='', nullable=False),
    sa.Column('notes', sa.Text(), server_default='', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assets')),
    sa.UniqueConstraint('tag', name=op.f('uq_assets_tag'))
    )
    op.create_table('jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='queued', nullable=False),
    sa.Column('progress', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name=op.f('ck_jobs_status_valid')),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_jobs_created_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_jobs_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs'))
    )
    op.create_index(op.f('ix_jobs_document_id'), 'jobs', ['document_id'], unique=False)
    op.create_table('asset_events',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('asset_tag', sa.String(length=32), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('label', sa.String(length=128), nullable=False),
    sa.Column('value', sa.Float(), nullable=True),
    sa.Column('unit', sa.String(length=16), nullable=True),
    sa.Column('detail', sa.Text(), server_default='', nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('chunk_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('failure', 'action', 'measurement', 'reading')", name=op.f('ck_asset_events_kind_valid')),
    sa.ForeignKeyConstraint(['chunk_id'], ['chunks.id'], name=op.f('fk_asset_events_chunk_id_chunks'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_asset_events_document_id_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_asset_events'))
    )
    op.create_index('ix_asset_events_asset_tag_event_date', 'asset_events', ['asset_tag', 'event_date'], unique=False)
    op.create_index(op.f('ix_asset_events_chunk_id'), 'asset_events', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_asset_events_document_id'), 'asset_events', ['document_id'], unique=False)
    op.add_column('chunks', sa.Column('section', sa.String(length=200), server_default='', nullable=False))
    op.add_column('chunks', sa.Column('word_count', sa.Integer(), server_default=sa.text('0'), nullable=False))
    # Autogenerate does not see CHECK constraint changes: allow the new 'queued' status.
    op.drop_constraint(op.f('ck_documents_status_valid'), 'documents', type_='check')
    op.create_check_constraint(op.f('ck_documents_status_valid'), 'documents', "status IN ('queued', 'processing', 'ready', 'failed')")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_documents_status_valid'), 'documents', type_='check')
    op.create_check_constraint(op.f('ck_documents_status_valid'), 'documents', "status IN ('processing', 'ready', 'failed')")
    op.drop_column('chunks', 'word_count')
    op.drop_column('chunks', 'section')
    op.drop_index(op.f('ix_asset_events_document_id'), table_name='asset_events')
    op.drop_index(op.f('ix_asset_events_chunk_id'), table_name='asset_events')
    op.drop_index('ix_asset_events_asset_tag_event_date', table_name='asset_events')
    op.drop_table('asset_events')
    op.drop_index(op.f('ix_jobs_document_id'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('assets')
