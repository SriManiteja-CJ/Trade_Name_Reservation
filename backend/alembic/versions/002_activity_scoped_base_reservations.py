"""Persist extracted base-name keys and enforce activity-scoped uniqueness.

Revision ID: 002_base_reservations
Revises: 001_initial_schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_base_reservations"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from pipeline.base_name_extractor import canonical_base_name

    op.add_column("trade_name_index", sa.Column("base_name_en", sa.Text(), nullable=True))
    op.add_column("trade_name_index", sa.Column("base_name_ar", sa.Text(), nullable=True))

    connection = op.get_bind()
    records = connection.execute(
        sa.text(
            "SELECT trade_name_id, category_id, normalized_en, normalized_ar "
            "FROM trade_name_index WHERE status IN ('active', 'reserved')"
        )
    ).mappings().all()
    keys_by_record: dict[int, tuple[str | None, str | None]] = {}
    records_by_key_en: dict[tuple[int, str], set[int]] = {}
    records_by_key_ar: dict[tuple[int, str], set[int]] = {}

    for row in records:
        category_id = row["category_id"]
        base_en = canonical_base_name(row["normalized_en"], lang="en")
        base_ar = canonical_base_name(row["normalized_ar"], lang="ar")
        if category_id is not None and base_en:
            key = (category_id, base_en)
            records_by_key_en.setdefault(key, set()).add(row["trade_name_id"])
        if category_id is not None and base_ar:
            key = (category_id, base_ar)
            records_by_key_ar.setdefault(key, set()).add(row["trade_name_id"])
        keys_by_record[row["trade_name_id"]] = (base_en, base_ar)

    conflicting_keys_en = {
        key for key, trade_name_ids in records_by_key_en.items() if len(trade_name_ids) > 1
    }
    conflicting_keys_ar = {
        key for key, trade_name_ids in records_by_key_ar.items() if len(trade_name_ids) > 1
    }

    if conflicting_keys_en or conflicting_keys_ar:
        from logging import getLogger

        getLogger("alembic.runtime.migration").warning(
            "Preserving active/reserved records with duplicate base-name keys; "
            "their conflicting keys will remain unset while runtime validation "
            "continues to check existing names."
        )

    for row in records:
        base_en, base_ar = keys_by_record[row["trade_name_id"]]
        category_id = row["category_id"]
        if category_id is not None and base_en and (category_id, base_en) in conflicting_keys_en:
            base_en = None
        if category_id is not None and base_ar and (category_id, base_ar) in conflicting_keys_ar:
            base_ar = None
        connection.execute(
            sa.text(
                "UPDATE trade_name_index SET base_name_en = :base_en, base_name_ar = :base_ar "
                "WHERE trade_name_id = :trade_name_id"
            ),
            {"base_en": base_en, "base_ar": base_ar, "trade_name_id": row["trade_name_id"]},
        )

    op.create_index(
        "uq_tni_active_cat_base_en",
        "trade_name_index",
        ["category_id", "base_name_en"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('active', 'reserved') AND category_id IS NOT NULL "
            "AND base_name_en IS NOT NULL AND base_name_en != ''"
        ),
        sqlite_where=sa.text(
            "status IN ('active', 'reserved') AND category_id IS NOT NULL "
            "AND base_name_en IS NOT NULL AND base_name_en != ''"
        ),
    )
    op.create_index(
        "uq_tni_active_cat_base_ar",
        "trade_name_index",
        ["category_id", "base_name_ar"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('active', 'reserved') AND category_id IS NOT NULL "
            "AND base_name_ar IS NOT NULL AND base_name_ar != ''"
        ),
        sqlite_where=sa.text(
            "status IN ('active', 'reserved') AND category_id IS NOT NULL "
            "AND base_name_ar IS NOT NULL AND base_name_ar != ''"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_tni_active_cat_base_ar", table_name="trade_name_index")
    op.drop_index("uq_tni_active_cat_base_en", table_name="trade_name_index")
    op.drop_column("trade_name_index", "base_name_ar")
    op.drop_column("trade_name_index", "base_name_en")
