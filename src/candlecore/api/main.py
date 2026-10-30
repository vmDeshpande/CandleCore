from candlecore.api.deps import set_application
from candlecore.application.orchestrator import CandleCoreApplication

application = CandleCoreApplication()
set_application(application)

app = application.app
