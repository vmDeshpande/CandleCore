import uuid

from sqlalchemy import JSON, Column, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

class RawMarketEvent(Base):
    __tablename__ = "raw_market_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    processed_at = Column(DateTime(timezone=True))
    original_timestamp = Column(Integer)
    original_timestamp_unit = Column(String)
    sequence = Column(Integer)
    schema_version = Column(Integer, default=1)
    payload = Column(JSON, nullable=False)

class Candle(Base):
    __tablename__ = "candles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    source = Column(String, nullable=False)
    candle_open_time = Column(DateTime(timezone=True), nullable=False)
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(20, 8))
    state = Column(String, nullable=False)
    revision = Column(Integer, default=0)
    first_received_at = Column(DateTime(timezone=True), nullable=False)
    last_received_at = Column(DateTime(timezone=True), nullable=False)
    finalized_at = Column(DateTime(timezone=True))
    reconciled_at = Column(DateTime(timezone=True))

class CandleRevision(Base):
    __tablename__ = "candle_revisions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candle_id = Column(UUID(as_uuid=True), nullable=False)
    revision_number = Column(Integer, nullable=False)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    candle_open_time = Column(DateTime(timezone=True), nullable=False)
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(20, 8))
    reason = Column(String)
    revised_at = Column(DateTime(timezone=True), nullable=False)
    raw_payload = Column(JSON)

class DataGap(Base):
    __tablename__ = "data_gaps"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    gap_start = Column(DateTime(timezone=True), nullable=False)
    gap_end = Column(DateTime(timezone=True), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    filled_at = Column(DateTime(timezone=True))
    fill_status = Column(String, default="detected")

class IngestionCheckpoint(Base):
    __tablename__ = "ingestion_checkpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    last_processed_time = Column(DateTime(timezone=True), nullable=False)
    watermark = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
