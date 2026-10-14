"""vector index and primary contact constraint

Revision ID: 0f202ce078a0
Revises: 686c1913be34
Create Date: 2026-08-13 06:57:00.659303

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f202ce078a0'
down_revision: Union[str, None] = '686c1913be34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # HNSW index for cosine-distance nearest-neighbor search over face
    # embeddings during live recognition. Built after confirming the
    # embedding dimension (512, matching Settings.face_embedding_dim) and
    # that cosine distance is the intended similarity metric for AdaFace
    # embeddings. Chosen over ivfflat because ivfflat requires the table to
    # already hold representative data at index-build time to size lists
    # correctly; HNSW does not have that requirement and is a better fit
    # for a table that starts empty.
    op.execute(
        "CREATE INDEX ix_face_embeddings_embedding_hnsw "
        "ON face_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    # A student may have several contacts (STUDENT/FATHER/MOTHER/GUARDIAN)
    # but at most one marked as the primary contact. This can't be a plain
    # column-level UNIQUE constraint (that would allow only one non-primary
    # row too), so it's a partial unique index on is_primary = true.
    op.execute(
        "CREATE UNIQUE INDEX uq_student_contacts_one_primary "
        "ON student_contacts (student_id) WHERE is_primary = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_student_contacts_one_primary")
    op.execute("DROP INDEX IF EXISTS ix_face_embeddings_embedding_hnsw")
