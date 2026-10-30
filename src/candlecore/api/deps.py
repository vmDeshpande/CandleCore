from typing import cast

from fastapi import Request

from candlecore.application.orchestrator import CandleCoreApplication

_application: CandleCoreApplication | None = None


def set_application(application: CandleCoreApplication) -> None:
    global _application
    _application = application


def get_application() -> CandleCoreApplication:
    if _application is None:
        raise RuntimeError("CandleCore application has not been initialized")
    return _application


def application_from_request(request: Request) -> CandleCoreApplication:
    app_state = getattr(request.app.state, "application", None)
    if app_state is not None:
        return cast(CandleCoreApplication, app_state)
    return get_application()
