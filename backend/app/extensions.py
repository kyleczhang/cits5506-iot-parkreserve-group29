"""Shared Flask extension instances for the ParkReserve backend.

This module defines the ORM base class and creates long-lived Flask extension
singletons that are initialised later during application bootstrap. Keeping
them in one place avoids circular imports and gives the rest of the codebase a
stable import surface for database, JWT, and Socket.IO integrations.
"""

from __future__ import annotations

from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base used by all SQLAlchemy models in the project."""

    pass


# SQLAlchemy registry and session manager.
db = SQLAlchemy(model_class=Base)
# JWT extension.
jwt = JWTManager()
# Socket.IO server.
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
