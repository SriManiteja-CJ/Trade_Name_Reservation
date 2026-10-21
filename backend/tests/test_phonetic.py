"""
tests/test_phonetic.py
Unit tests for cross-script phonetic key generator (index/phonetic.py).

Spec references:
  E2 — Phonetic matching across scripts (Noor = Nour = النور)
  §3 Component ③ — cross-script phonetic key
"""
import pytest
from index.phonetic import generate_phonetic_key, generate_phonetic_key_pair


def test_phonetic_arabic_skeleton():
    """Verify Arabic text produces consonant skeleton."""
    key = generate_phonetic_key("نور")
    assert key == "NWR"


def test_phonetic_english_variations():
    """Verify Noor and Nour produce identical or closely matched English phonetic keys."""
    key_noor = generate_phonetic_key("Noor")
    key_nour = generate_phonetic_key("Nour")
    assert key_noor == "N0R"
    assert key_nour == "N0R"


def test_phonetic_key_pair_generation():
    """Verify generate_phonetic_key_pair combines both into AR|EN format."""
    pair_key = generate_phonetic_key_pair("نور", "Nour")
    assert pair_key == "NWR|N0R"
