"""Shared pytest helpers."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient


def app_client(app) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client
