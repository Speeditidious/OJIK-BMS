"""Fix clear_type values to match new internal mapping

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-12

Remaps stored clear_type values in user_scores and score_history to use the
new internal clear type system where numeric order equals quality order:
  0=NO PLAY, 1=FAILED, 2=ASSIST, 3=EASY, 4=NORMAL,
  5=HARD, 6=EXHARD, 7=FC, 8=PERFECT, 9=MAX

LR2: DB types 2-5 mapped incorrectly (old mapping was identity 2→2, 3→3, ...
     but correct is 2→3 EASY, 3→4 NORMAL, 4→5 HARD, 5→7 FC)
Beatoraja: DB types were stored as identity (0→0, 1→1, ...) but correct
     mapping shifts types 3-10 to internal 2-9.
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- LR2 user_scores ---
    # Process highest → lowest to avoid collision chains
    op.execute(
        "UPDATE user_scores SET clear_type = 9 WHERE client_type = 'lr2' AND clear_type = 7"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 8 WHERE client_type = 'lr2' AND clear_type = 6"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 7 WHERE client_type = 'lr2' AND clear_type = 5"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 5 WHERE client_type = 'lr2' AND clear_type = 4"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 4 WHERE client_type = 'lr2' AND clear_type = 3"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 3 WHERE client_type = 'lr2' AND clear_type = 2"
    )

    # --- LR2 score_history ---
    for col in ("clear_type", "old_clear_type"):
        op.execute(
            f"UPDATE score_history SET {col} = 9 WHERE client_type = 'lr2' AND {col} = 7"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 8 WHERE client_type = 'lr2' AND {col} = 6"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 7 WHERE client_type = 'lr2' AND {col} = 5"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 5 WHERE client_type = 'lr2' AND {col} = 4"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 4 WHERE client_type = 'lr2' AND {col} = 3"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 3 WHERE client_type = 'lr2' AND {col} = 2"
        )

    # --- Beatoraja user_scores ---
    op.execute(
        "UPDATE user_scores SET clear_type = 9 WHERE client_type = 'beatoraja' AND clear_type = 10"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 8 WHERE client_type = 'beatoraja' AND clear_type = 9"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 7 WHERE client_type = 'beatoraja' AND clear_type = 8"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 6 WHERE client_type = 'beatoraja' AND clear_type = 7"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 5 WHERE client_type = 'beatoraja' AND clear_type = 6"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 4 WHERE client_type = 'beatoraja' AND clear_type = 5"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 3 WHERE client_type = 'beatoraja' AND clear_type = 4"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 2 WHERE client_type = 'beatoraja' AND clear_type = 3"
    )
    # Beatoraja DB type 2 (no-score failed) → internal 1 (same as type 1)
    op.execute(
        "UPDATE user_scores SET clear_type = 1 WHERE client_type = 'beatoraja' AND clear_type = 2"
    )

    # --- Beatoraja score_history ---
    for col in ("clear_type", "old_clear_type"):
        op.execute(
            f"UPDATE score_history SET {col} = 9 WHERE client_type = 'beatoraja' AND {col} = 10"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 8 WHERE client_type = 'beatoraja' AND {col} = 9"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 7 WHERE client_type = 'beatoraja' AND {col} = 8"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 6 WHERE client_type = 'beatoraja' AND {col} = 7"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 5 WHERE client_type = 'beatoraja' AND {col} = 6"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 4 WHERE client_type = 'beatoraja' AND {col} = 5"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 3 WHERE client_type = 'beatoraja' AND {col} = 4"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 2 WHERE client_type = 'beatoraja' AND {col} = 3"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 1 WHERE client_type = 'beatoraja' AND {col} = 2"
        )


def downgrade() -> None:
    # Reverse LR2 user_scores (lowest → highest to avoid collisions)
    op.execute(
        "UPDATE user_scores SET clear_type = 2 WHERE client_type = 'lr2' AND clear_type = 3"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 3 WHERE client_type = 'lr2' AND clear_type = 4"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 4 WHERE client_type = 'lr2' AND clear_type = 5"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 5 WHERE client_type = 'lr2' AND clear_type = 7"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 6 WHERE client_type = 'lr2' AND clear_type = 8"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 7 WHERE client_type = 'lr2' AND clear_type = 9"
    )

    for col in ("clear_type", "old_clear_type"):
        op.execute(
            f"UPDATE score_history SET {col} = 2 WHERE client_type = 'lr2' AND {col} = 3"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 3 WHERE client_type = 'lr2' AND {col} = 4"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 4 WHERE client_type = 'lr2' AND {col} = 5"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 5 WHERE client_type = 'lr2' AND {col} = 7"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 6 WHERE client_type = 'lr2' AND {col} = 8"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 7 WHERE client_type = 'lr2' AND {col} = 9"
        )

    # Reverse Beatoraja user_scores
    op.execute(
        "UPDATE user_scores SET clear_type = 2 WHERE client_type = 'beatoraja' AND clear_type = 1"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 3 WHERE client_type = 'beatoraja' AND clear_type = 2"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 4 WHERE client_type = 'beatoraja' AND clear_type = 3"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 5 WHERE client_type = 'beatoraja' AND clear_type = 4"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 6 WHERE client_type = 'beatoraja' AND clear_type = 5"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 7 WHERE client_type = 'beatoraja' AND clear_type = 6"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 8 WHERE client_type = 'beatoraja' AND clear_type = 7"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 9 WHERE client_type = 'beatoraja' AND clear_type = 8"
    )
    op.execute(
        "UPDATE user_scores SET clear_type = 10 WHERE client_type = 'beatoraja' AND clear_type = 9"
    )

    for col in ("clear_type", "old_clear_type"):
        op.execute(
            f"UPDATE score_history SET {col} = 2 WHERE client_type = 'beatoraja' AND {col} = 1"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 3 WHERE client_type = 'beatoraja' AND {col} = 2"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 4 WHERE client_type = 'beatoraja' AND {col} = 3"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 5 WHERE client_type = 'beatoraja' AND {col} = 4"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 6 WHERE client_type = 'beatoraja' AND {col} = 5"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 7 WHERE client_type = 'beatoraja' AND {col} = 6"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 8 WHERE client_type = 'beatoraja' AND {col} = 7"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 9 WHERE client_type = 'beatoraja' AND {col} = 8"
        )
        op.execute(
            f"UPDATE score_history SET {col} = 10 WHERE client_type = 'beatoraja' AND {col} = 9"
        )
