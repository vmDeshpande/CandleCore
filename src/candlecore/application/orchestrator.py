from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from candlecore.application.gap_recovery import GapRecoveryService
from candlecore.application.ingestion import IngestionService
from candlecore.core.config import get_settings
from candlecore.core.logging import configure_logging
from candlecore.exchange.delta.rest_client import DeltaRestClient
from candlecore.exchange.delta.ws_client import DeltaWebSocketClient
from candlecore.market_data.lifecycle import CandleLifecycleEngine
from candlecore.storage.database import dispose_db, init_db
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

    async def startup(self) -> None:
        if self._started:
            return
        await init_db()
        self._started = True

    async def shutdown(self) -> None:
        if not self._started:
            return
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
