"""
tests/test_name_composer.py
Unit tests for NameComposer (pipeline/name_composer.py).

Spec references:
  F10 — Outside-UAQ branches get suffix "Umm Al Quwain Branch" / "فرع أم القيوين"
  F11 — Legal-form amendment swaps old legal form for new
  F12 — Unchanged name exemption sets skip_word_checks=True
  F8  — Legal form display requirement
"""
import pytest
from pipeline.name_composer import (
    BRANCH_SUFFIX_AR,
    BRANCH_SUFFIX_EN,
    compose,
)


def test_compose_standard_new_name():
    """Verify regular new name without branch or amendment passes through unchanged."""
    res = compose(
        name_ar="الرواد للاستشارات",
        name_en="Al Rowad Consulting",
        operation_type="new",
    )
    assert res.branch is False
    assert res.skip_word_checks is False
    assert "الرواد للاستشارات" in res.effective_ar
    assert "Al Rowad Consulting" in res.effective_en


def test_compose_outside_uaq_branch_suffix_f10():
    """Verify F10: outside-UAQ branch appends the exact branch suffix."""
    res = compose(
        name_ar="الرواد للاستشارات",
        name_en="Al Rowad Consulting",
        operation_type="branch",
        is_outside_uaq=True,
    )
    assert res.branch is True
    assert BRANCH_SUFFIX_EN.lower() in res.normalized_en
    assert "فرع ام القيوين" in res.normalized_ar


def test_compose_legal_form_amendment_swap_f11():
    """Verify F11: legal-form amendment swaps old legal form for new."""
    res = compose(
        name_ar="شركة الأمل للتجارة ذ.م.م",
        name_en="Al Amal Trading LLC",
        operation_type="legal_form_amend",
        old_legal_form="LLC",
        new_legal_form="PJSC",
    )
    assert "pjsc" in res.normalized_en
    assert "llc" not in res.normalized_en


def test_compose_unchanged_name_exemption_f12():
    """Verify F12: unchanged name sets skip_word_checks=True."""
    res = compose(
        name_ar="مؤسسة النخبة",
        name_en="Al Nokhba Est",
        operation_type="legal_form_amend",
        previous_name_ar="مؤسسة النخبة",
        previous_name_en="Al Nokhba Est",
    )
    assert res.skip_word_checks is True


def test_compose_changed_name_does_not_get_f12_exemption():
    """Verify changed name does NOT skip word checks."""
    res = compose(
        name_ar="مؤسسة النخبة الجديدة",
        name_en="Al Nokhba New Est",
        operation_type="edit",
        previous_name_ar="مؤسسة النخبة",
        previous_name_en="Al Nokhba Est",
    )
    assert res.skip_word_checks is False


def test_compose_legal_form_display_f8():
    """Verify LLC / ذ.م.م triggers show_legal_form=True."""
    res = compose(
        name_ar="شركة النور للتجارة ذ.م.م",
        name_en="Al Noor Trading LLC",
        operation_type="new",
    )
    assert res.show_legal_form is True
