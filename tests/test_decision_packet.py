"""Tests pour build_decision_packet, notamment impulse_memory."""
import os

import pytest

from app.agents import build_decision_packet
from app.providers.mock import MockDataProvider


def test_build_decision_packet_impulse_memory_defined():
    """
    Vérifie que build_decision_packet ne lève pas NameError sur impulse_memory.
    Le bug précédent : impulse_memory utilisé dans _make_packet sans être défini.
    """
    os.environ.pop("MOCK_PROVIDER_FAIL", None)
    os.environ.pop("MOCK_SERVER_TIME_UTC", None)
    provider = MockDataProvider()
    packet = build_decision_packet(provider, "XAUUSD")
    assert packet is not None
    state = packet.state or {}
    # impulse_memory peut être un dict ou None selon les bougies
    imp = state.get("impulse_memory")
    assert imp is None or isinstance(imp, dict)
    if imp is not None:
        assert "last_impulse_dir" in imp
        assert "impulse_anchor_price" in imp
