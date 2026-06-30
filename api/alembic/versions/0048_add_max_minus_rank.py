"""Add MAX- score rank and backfill stored score ranks."""

from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH score_notes AS (
            SELECT
                us.id,
                us.exscore,
                COALESCE(
                    f.notes_total,
                    CASE
                        WHEN us.client_type = 'lr2' AND us.judgments IS NOT NULL THEN
                            COALESCE((us.judgments->>'perfect')::integer, 0)
                            + COALESCE((us.judgments->>'great')::integer, 0)
                            + COALESCE((us.judgments->>'good')::integer, 0)
                            + COALESCE((us.judgments->>'bad')::integer, 0)
                            + COALESCE((us.judgments->>'poor')::integer, 0)
                    END,
                    CASE
                        WHEN us.client_type = 'beatoraja' AND us.judgments IS NOT NULL THEN
                            COALESCE((us.judgments->>'epg')::integer, 0)
                            + COALESCE((us.judgments->>'lpg')::integer, 0)
                            + COALESCE((us.judgments->>'egr')::integer, 0)
                            + COALESCE((us.judgments->>'lgr')::integer, 0)
                            + COALESCE((us.judgments->>'egd')::integer, 0)
                            + COALESCE((us.judgments->>'lgd')::integer, 0)
                            + COALESCE((us.judgments->>'ebd')::integer, 0)
                            + COALESCE((us.judgments->>'lbd')::integer, 0)
                            + COALESCE((us.judgments->>'epr')::integer, 0)
                            + COALESCE((us.judgments->>'lpr')::integer, 0)
                            + COALESCE((us.judgments->>'ems')::integer, 0)
                            + COALESCE((us.judgments->>'lms')::integer, 0)
                    END
                ) AS notes
            FROM user_scores us
            LEFT JOIN fumens f ON f.fumen_id = us.fumen_id
            WHERE us.exscore IS NOT NULL
        ),
        recalculated AS (
            SELECT
                id,
                CASE
                    WHEN exscore * 9 >= notes * 17 THEN 'MAX-'
                    WHEN exscore * 9 >= notes * 16 THEN 'AAA'
                    WHEN exscore * 9 >= notes * 14 THEN 'AA'
                    WHEN exscore * 9 >= notes * 12 THEN 'A'
                    WHEN exscore * 9 >= notes * 10 THEN 'B'
                    WHEN exscore * 9 >= notes * 8 THEN 'C'
                    WHEN exscore * 9 >= notes * 6 THEN 'D'
                    WHEN exscore * 9 >= notes * 4 THEN 'E'
                    ELSE 'F'
                END AS rank
            FROM score_notes
            WHERE notes IS NOT NULL AND notes > 0
        )
        UPDATE user_scores us
           SET rank = recalculated.rank
          FROM recalculated
         WHERE us.id = recalculated.id
           AND us.rank IS DISTINCT FROM recalculated.rank
        """
    )


def downgrade() -> None:
    op.execute("UPDATE user_scores SET rank = 'AAA' WHERE rank = 'MAX-'")
