"""Recalculate course score ranks with summed member notes."""

from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH md5_members AS (
            SELECT c.id AS course_id, m.md5, m.ord, f.notes_total
              FROM courses c
              JOIN LATERAL jsonb_array_elements_text(
                  CASE WHEN jsonb_typeof(c.md5_list) = 'array' THEN c.md5_list ELSE '[]'::jsonb END
              ) WITH ORDINALITY AS m(md5, ord) ON TRUE
              LEFT JOIN fumens f ON f.md5 = m.md5
        ),
        md5_course_notes AS (
            SELECT
                course_id,
                string_agg(md5, '' ORDER BY ord) AS md5_concat,
                SUM(notes_total) AS notes,
                COUNT(*) AS member_count,
                COUNT(notes_total) AS known_note_count
            FROM md5_members
            GROUP BY course_id
        ),
        sha256_concats AS (
            SELECT
                c.id AS course_id,
                string_agg(s.sha256, '' ORDER BY s.ord) AS sha256_concat,
                COUNT(*) AS sha256_count,
                COUNT(*) FILTER (WHERE s.sha256 IS NOT NULL AND s.sha256 <> 'null') AS known_sha256_count
            FROM courses c
            LEFT JOIN LATERAL jsonb_array_elements_text(
                CASE WHEN jsonb_typeof(c.sha256_list) = 'array' THEN c.sha256_list ELSE '[]'::jsonb END
            ) WITH ORDINALITY AS s(sha256, ord) ON TRUE
            GROUP BY c.id
        ),
        course_notes AS (
            SELECT
                m.course_id,
                m.md5_concat,
                CASE
                    WHEN s.sha256_count = m.member_count AND s.known_sha256_count = m.member_count
                    THEN s.sha256_concat
                    ELSE NULL
                END AS sha256_concat,
                m.notes
            FROM md5_course_notes m
            LEFT JOIN sha256_concats s ON s.course_id = m.course_id
            WHERE m.member_count > 0
              AND m.known_note_count = m.member_count
              AND m.notes > 0
        ),
        matched_scores AS (
            SELECT
                us.id,
                us.exscore,
                cn.notes
            FROM user_scores us
            JOIN course_notes cn ON (
                (us.client_type = 'lr2' AND us.fumen_hash_others LIKE '%' || cn.md5_concat)
                OR (
                    us.client_type = 'beatoraja'
                    AND cn.sha256_concat IS NOT NULL
                    AND us.fumen_hash_others = cn.sha256_concat
                )
            )
            WHERE us.fumen_hash_others IS NOT NULL
              AND us.exscore IS NOT NULL
        ),
        recalculated AS (
            SELECT
                id,
                floor((exscore::numeric / (notes * 2)::numeric) * 10000) / 100 AS rate,
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
            FROM matched_scores
        )
        UPDATE user_scores us
           SET rate = recalculated.rate,
               rank = recalculated.rank
          FROM recalculated
         WHERE us.id = recalculated.id
           AND (
               us.rate IS DISTINCT FROM recalculated.rate
               OR us.rank IS DISTINCT FROM recalculated.rank
           )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE user_scores
           SET rank = NULL
         WHERE fumen_hash_others IS NOT NULL
        """
    )
