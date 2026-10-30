from candlecore.api.deps import set_application
from candlecore.application.orchestrator import CandleCoreApplication

application = CandleCoreApplication()
set_application(application)

app = application.app

# Include stream router
from candlecore.api.routes import stream

app.include_router(stream.router, prefix="/api/v1/stream")
