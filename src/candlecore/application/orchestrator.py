import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from candlecore.api.routes import stream
from candlecore.application.gap_recovery import GapRecoveryService
from candlecore.application.ingestion import IngestionService
from candlecore.core.config import get_settings
from candlecore.core.logging import configure_logging
from candlecore.exchange.delta.rest_client import DeltaRestClient
from candlecore.exchange.delta.ws_client import DeltaWebSocketClient
from candlecore.market_data.lifecycle import CandleLifecycleEngine
from candlecore.market_data.normalization import normalize_ws_message
from candlecore.storage.database import dispose_db, get_db_session, init_db
from candlecore.storage.repositories import (
    CandleRepository,
    CandleRevisionRepository,
    DataGapRepository,
    IngestionCheckpointRepository,
    RawMarketEventRepository,
)


class CandleCoreApplication:
    def __init__(self) -> None:
        self.settings = get_settings()
        configure_logging()
        self.rest_client = DeltaRestClient(
            base_url=self.settings.delta_rest_base_url,
            timeout=self.settings.http_timeout,
            max_retries=self.settings.http_max_retries,
            base_delay=self.settings.http_base_delay,
            max_delay=self.settings.http_max_delay,
        )
        self.ws_client = DeltaWebSocketClient(
            ws_url=self.settings.delta_ws_url,
            symbols=self.settings.symbol_list,
            channel="candlestick_3m",
        )
        self._started = False
        self._collector_task: asyncio.Task[None] | None = None
        self._backfill_task: asyncio.Task[None] | None = None
        self.app = self._build_app()

    def _build_app(self) -> FastAPI:
        from candlecore.api.routes import health, market

        app = FastAPI(title="CandleCore", version="0.1.0")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        app.include_router(health.router, prefix="/api/v1")
        app.include_router(market.router, prefix="/api/v1")

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            await self.startup()
            try:
                yield
            finally:
                await self.shutdown()

        app.router.lifespan_context = lifespan
        return app

    async def _handle_ws_message(self, message: dict[str, Any]) -> None:
        try:
            symbol = message.get("symbol") or message.get("product_symbol")
            if isinstance(symbol, str):
                symbol = symbol.upper()
            else:
                # try payload
                payload = message.get("payload")
                if isinstance(payload, dict):
                    symbol = payload.get("symbol") or payload.get("product_symbol")
                    if isinstance(symbol, str):
                        symbol = symbol.upper()
            if symbol not in self.settings.symbol_list:
                return
            timeframe = "3m"
            async for session in get_db_session():
                services = self.build_services(session)
                ingestion: IngestionService = services["ingestion"]
                result = await ingestion.ingest_ws_message(
                    exchange="delta",
                    symbol=symbol,
                    timeframe=timeframe,
                    source="exchange_ws",
                    message=message,
                    timestamp_unit="seconds",
                )
                await session.commit()
                # Broadcast to frontend clients
                try:
                    update = normalize_ws_message(
                        exchange="delta",
                        symbol=symbol,
                        timeframe=timeframe,
                        source="exchange_ws",
                        message=message,
                        timestamp_unit="seconds",
                    )
                    await stream.manager.broadcast(
                        {
                            "type": "candle",
                            "exchange": "delta",
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "candle_open_time": update.candle_open_time.isoformat(),
                            "open": str(update.open),
                            "high": str(update.high),
                            "low": str(update.low),
                            "close": str(update.close),
                            "volume": str(update.volume) if update.volume is not None else None,
                            "state": result.state.value
                            if hasattr(result.state, "value")
                            else str(result.state),
                            "revision": result.revision,
                        }
                    )
                except Exception:
                    pass
                break
        except Exception:
            pass

    async def _backfill_historical(self) -> None:
        try:
            async for session in get_db_session():
                services = self.build_services(session)
                ingestion: IngestionService = services["ingestion"]
                for symbol in self.settings.symbol_list:
                    try:
                        candles = await self.rest_client.get_candles_chunked(
                            symbol=symbol,
                            resolution="3m",
                            start=0,
                            end=2000000000,
                        )
                        # get_candles_chunked requires start < end; better to fetch recent window
                    except Exception:
                        candles = []
                    # fetch recent window properly
                    try:
                        from datetime import datetime

                        end_ts = int(datetime.now().timestamp())
                        start_ts = end_ts - 7 * 24 * 3600
                        candles = await self.rest_client.get_candles_chunked(
                            symbol=symbol,
                            resolution="3m",
                            start=start_ts,
                            end=end_ts,
                        )
                    except Exception:
                        candles = []
                    for c in candles:
                        try:
                            await ingestion.ingest_rest_candle(
                                exchange="delta",
                                symbol=symbol,
                                timeframe="3m",
                                source="exchange_rest",
                                candle=c,
                                timestamp_unit="seconds",
                            )
                        except Exception:
                            continue
                    await session.commit()
                break
        except Exception:
            pass

    async def startup(self) -> None:
        if self._started:
            return
        await init_db()
        self._started = True
        # Attach message handler
        self.ws_client.on_message = self._handle_ws_message  # type: ignore[assignment]
        # Start collector
        if self._collector_task is None or self._collector_task.done():
            self._collector_task = asyncio.create_task(self.ws_client.start())
        # Start backfill
        if self._backfill_task is None or self._backfill_task.done():
            self._backfill_task = asyncio.create_task(self._backfill_historical())

    async def shutdown(self) -> None:
        if not self._started:
            return
        if self._backfill_task is not None:
            self._backfill_task.cancel()
            self._backfill_task = None
        if self._collector_task is not None:
            self._collector_task.cancel()
            self._collector_task = None
        await self.ws_client.stop()
        await self.rest_client.close()
        await dispose_db()
        self._started = False

    def build_services(
        self,
        session: Any,
        process_candle: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        candle_repo = CandleRepository(session)
        revision_repo = CandleRevisionRepository(session)
        raw_event_repo = RawMarketEventRepository(session)
        checkpoint_repo = IngestionCheckpointRepository(session)
        gap_repo = DataGapRepository(session)

        lifecycle_engine = CandleLifecycleEngine(candle_repo, revision_repo)
        ingestion_service = IngestionService(
            candle_repository=candle_repo,
            revision_repository=revision_repo,
            raw_event_repository=raw_event_repo,
            checkpoint_repository=checkpoint_repo,
            lifecycle_engine=lifecycle_engine,
        )
        gap_recovery = GapRecoveryService(
            rest_client=self.rest_client,
            candle_repository=candle_repo,
            gap_repository=gap_repo,
            checkpoint_repository=checkpoint_repo,
            process_candle=process_candle,
            exchange="delta",
        )
        return {
            "candle": candle_repo,
            "revision": revision_repo,
            "raw_event": raw_event_repo,
            "checkpoint": checkpoint_repo,
            "gap": gap_repo,
            "lifecycle": lifecycle_engine,
            "ingestion": ingestion_service,
            "gap_recovery": gap_recovery,
            "rest_client": self.rest_client,
            "ws_client": self.ws_client,
        }
