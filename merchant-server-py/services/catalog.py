"""
services/catalog.py — mirrors internal/services/catalog.go
Searches products table with the same SQL logic as Go: ILIKE on name,
description AND unnest(tags), category and price_paise filters, ORDER BY
price_paise ASC LIMIT 20.
"""
import asyncpg
from models import Product


class CatalogService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def search(
        self,
        query: str        = "",
        category: str     = "",
        max_price_paise: int = 0,
    ) -> list[Product]:
        # Build dynamic query exactly as Go does with fmt.Sprintf + args slice
        sql  = "SELECT id, name, description, category, price_paise, stock, tags, image_url, created_at FROM products WHERE 1=1"
        args: list = []
        i    = 1

        if query:
            words = query.split()
            for word in words:
                sql += f"""
                    AND (
                        name ILIKE ${i}
                        OR description ILIKE ${i}
                        OR EXISTS (
                            SELECT 1 FROM unnest(tags) t WHERE t ILIKE ${i}
                        )
                    )"""
                args.append(f"%{word}%")
                i += 1


        if category:
            sql += f" AND category = ${i}"
            args.append(category)
            i += 1

        if max_price_paise > 0:
            sql += f" AND price_paise <= ${i}"
            args.append(max_price_paise)
            i += 1

        sql += " ORDER BY price_paise ASC LIMIT 20"

        rows = await self.pool.fetch(sql, *args)
        return [self._row_to_product(r) for r in rows]

    async def get_by_id(self, product_id: str) -> Product | None:
        row = await self.pool.fetchrow(
            """
            SELECT id, name, description, category, price_paise, stock, tags, image_url, created_at
            FROM products
            WHERE id = $1
            """,
            product_id,
        )
        if row is None:
            return None
        return self._row_to_product(row)

    @staticmethod
    def _row_to_product(row: asyncpg.Record) -> Product:
        return Product(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"] or "",
            category=row["category"] or "",
            price_paise=row["price_paise"],
            price_inr=row["price_paise"] / 100,
            stock=row["stock"],
            tags=list(row["tags"]) if row["tags"] else [],
            image_url=row["image_url"] or "",
            created_at=row["created_at"],
        )