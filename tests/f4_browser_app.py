"""Browser entrypoint using the merged F2/F3/F4 production composition."""
from app.core.ports import production_ports
from app.main import create_app


def make_ports():
    return production_ports()


def build():
    return create_app()
