"""Test-only composition of the real F2/F4 app and an optional actual F3 export."""
import os
import app.features
from app.core.ports import production_ports
from app.main import create_app, command, with_meta


def make_ports():
    ports = production_ports()
    if os.environ.get('SHIFTLINK_F3_FEATURE_ROOT'):
        app.features.__path__.append(os.environ['SHIFTLINK_F3_FEATURE_ROOT'])
        from app.features.handovers.service import refresh_handover_items
        ports.handover_refresher = refresh_handover_items
    return ports


def build():
    app = create_app(ports=make_ports())
    if os.environ.get('SHIFTLINK_F3_FEATURE_ROOT'):
        from app.features.handovers.router import register
        register(app, command=command, with_meta=with_meta)
    return app
