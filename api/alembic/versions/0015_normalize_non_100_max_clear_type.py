"""Normalize non-100 MAX clear types.

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-26
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE user_scores
           SET clear_type = 7
         WHERE client_type IN ('lr2', 'beatoraja')
           AND clear_type = 9
           AND (
                exscore = 0
                OR (
                    client_type = 'lr2'
                    AND judgments IS NOT NULL
                    AND (judgments ? 'perfect' OR judgments ? 'great')
                    AND (
                        COALESCE((judgments->>'perfect')::integer, 0) * 2
                        + COALESCE((judgments->>'great')::integer, 0)
                    ) = 0
                )
                OR (
                    client_type = 'beatoraja'
                    AND judgments IS NOT NULL
                    AND (
                        judgments ? 'epg'
                        OR judgments ? 'lpg'
                        OR judgments ? 'egr'
                        OR judgments ? 'lgr'
                    )
                    AND (
                        (
                            COALESCE((judgments->>'epg')::integer, 0)
                            + COALESCE((judgments->>'lpg')::integer, 0)
                        ) * 2
                        + COALESCE((judgments->>'egr')::integer, 0)
                        + COALESCE((judgments->>'lgr')::integer, 0)
                    ) = 0
                )
           )
        """
    )
    op.execute(
        """
        UPDATE user_scores
           SET clear_type = 8
         WHERE client_type IN ('lr2', 'beatoraja')
           AND clear_type = 9
           AND rate IS NOT NULL
           AND rate <> 100.0
           AND exscore > 0
        """
    )


def downgrade() -> None:
    pass
