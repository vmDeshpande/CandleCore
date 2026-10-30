"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-30 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_market_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_timestamp", sa.Integer(), nullable=True),
        sa.Column("original_timestamp_unit", sa.String(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_raw_market_events_exchange_symbol_time",
        "raw_market_events",
        ["exchange", "symbol", "event_time"],
    )
    op.create_index("ix_raw_market_events_received_at", "raw_market_events", ["received_at"])

    op.create_table(
        "candles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("candle_open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(20, 8), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=True),
        sa.Column("first_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange",
            "symbol",
            "timeframe",
            "candle_open_time",
            name="uq_candle_identity",
        ),
    )
    op.create_index(
        "ix_candles_symbol_timeframe_time",
        "candles",
        ["symbol", "timeframe", "candle_open_time"],
    )
    op.create_index(
        "ix_candles_exchange_symbol_timeframe_time",
        "candles",
        ["exchange", "symbol", "timeframe", "candle_open_time"],
    )

    op.create_table(
        "candle_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("candle_open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(20, 8), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("revised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["candle_id"], ["candles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candle_id", "revision_number", name="uq_candle_revision_number"),
    )
    op.create_index("ix_candle_revisions_candle_id", "candle_revisions", ["candle_id"])
    op.create_index(
        "ix_candle_revisions_candle_open_time",
        "candle_revisions",
        ["candle_open_time"],
    )

    op.create_table(
        "data_gaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("gap_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gap_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fill_status", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_gaps_symbol_timeframe_status",
        "data_gaps",
        ["symbol", "timeframe", "fill_status"],
    )
    op.create_index("ix_data_gaps_gap_start_gap_end", "data_gaps", ["gap_start", "gap_end"])

    op.create_table(
        "ingestion_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("last_processed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("watermark", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange",
            "symbol",
            "timeframe",
            name="uq_ingestion_checkpoint_identity",
        ),
    )
    op.create_index(
        "ix_ingestion_checkpoints_updated_at",
        "ingestion_checkpoints",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_checkpoints_updated_at", table_name="ingestion_checkpoints")
    op.drop_table("ingestion_checkpoints")
    op.drop_index("ix_data_gaps_gap_start_gap_end", table_name="data_gaps")
    op.drop_index("ix_data_gaps_symbol_timeframe_status", table_name="data_gaps")
    op.drop_table("data_gaps")
    op.drop_index("ix_candle_revisions_candle_open_time", table_name="candle_revisions")
    op.drop_index("ix_candle_revisions_candle_id", table_name="candle_revisions")
    op.drop_table("candle_revisions")
    op.drop_index("ix_candles_exchange_symbol_timeframe_time", table_name="candles")
    op.drop_index("ix_candles_symbol_timeframe_time", table_name="candles")
    op.drop_table("candles")
    op.drop_index("ix_raw_market_events_received_at", table_name="raw_market_events")
    op.drop_index("ix_raw_market_events_exchange_symbol_time", table_name="raw_market_events")
    op.drop_table("raw_market_events")
