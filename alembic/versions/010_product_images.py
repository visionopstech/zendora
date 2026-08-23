"""Create product_images, backfill from products.images, drop JSON column

Revision ID: 010_product_images
Revises: 009_default_gift_collections
Create Date: 2026-08-22 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "010_product_images"
down_revision: Union[str, None] = "009_default_gift_collections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_images",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_product_images_product_id", "product_images", ["product_id"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_product_images_primary
        ON product_images (product_id)
        WHERE is_primary
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            rec RECORD;
            img JSONB;
            idx INT;
            url TEXT;
            alt TEXT;
        BEGIN
            FOR rec IN
                SELECT id, images
                FROM products
                WHERE images IS NOT NULL
                  AND jsonb_typeof(images::jsonb) = 'array'
            LOOP
                idx := 0;
                FOR img IN SELECT value FROM jsonb_array_elements(rec.images::jsonb)
                LOOP
                    IF jsonb_typeof(img) = 'string' THEN
                        url := trim(both '"' FROM img::text);
                        alt := NULL;
                    ELSIF jsonb_typeof(img) = 'object' THEN
                        url := img->>'url';
                        alt := COALESCE(img->>'alt_text', img->>'alt');
                    ELSE
                        CONTINUE;
                    END IF;

                    IF url IS NULL OR url = '' THEN
                        CONTINUE;
                    END IF;

                    INSERT INTO product_images (product_id, url, alt_text, is_primary, sort_order)
                    VALUES (rec.id, url, alt, idx = 0, idx);

                    idx := idx + 1;
                END LOOP;
            END LOOP;
        END $$;
        """
    )

    op.drop_column("products", "images")


def downgrade() -> None:
    op.add_column("products", sa.Column("images", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE products AS p
        SET images = sub.urls
        FROM (
            SELECT
                product_id,
                jsonb_agg(url ORDER BY sort_order, created_at) AS urls
            FROM product_images
            GROUP BY product_id
        ) AS sub
        WHERE p.id = sub.product_id
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_product_images_primary")
    op.drop_index("idx_product_images_product_id", table_name="product_images")
    op.drop_table("product_images")
