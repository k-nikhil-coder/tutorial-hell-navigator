# PostgreSQL and psycopg2

## Transactions and Atomic Multi-table Inserts

To insert a parent row and its child rows atomically with psycopg2:

```python
import psycopg2

conn = psycopg2.connect(DSN)
try:
    with conn:                     # begins a transaction
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO listing (title) VALUES (%s) RETURNING listing_sk",
                (title,)
            )
            listing_id = cur.fetchone()[0]
            for rate in shipping_rates:
                cur.execute(
                    "INSERT INTO shipping_rate (listing_sk, amount) VALUES (%s, %s)",
                    (listing_id, rate)
                )
    # commit happens automatically on successful exit of the with block
except Exception:
    # rollback happens automatically
    raise
finally:
    conn.close()
```

Key points:

- Exiting a connection's `with` block commits if no exception occurred, otherwise rolls back.
- The connection itself is **not** closed by the context manager; you must call `conn.close()` yourself.
- Each nested `with conn:` starts a new transaction.

Alternative using `lastval()` / `currval()`:

```sql
INSERT INTO listing (title) VALUES (%s);
INSERT INTO shipping_rate (listing_sk, amount)
VALUES (currval(pg_get_serial_sequence('listing', 'listing_sk')), %s);
```

## InFailedSqlTransaction

After any error inside a transaction, PostgreSQL aborts the whole transaction. Subsequent commands on the same connection raise:

```
psycopg2.errors.InFailedSqlTransaction:
current transaction is aborted, commands ignored until end of transaction block
```

Recovery:

```python
conn.rollback()   # or let a context manager do it
# now you can start a new transaction
```

Always prefer context managers so that rollbacks happen automatically.

## Parameterized Queries and IN Lists

Never interpolate values with string formatting. Use placeholders:

```python
cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

For an `IN` list of variable length:

```python
ids = [1, 2, 3, 4]
cur.execute(
    "SELECT * FROM users WHERE id = ANY(%s)",
    (ids,)          # pass the list as a single parameter
)
# or
placeholders = ','.join(['%s'] * len(ids))
cur.execute(
    f"SELECT * FROM users WHERE id IN ({placeholders})",
    ids
)
```

## Connection Pooling Notes

Under load, opening a new TCP connection for every request is expensive. Use a pool (psycopg2.pool or an external pooler such as PgBouncer). Typical settings to inspect first when seeing timeouts:

- `maxconn` / pool size
- statement timeouts
- idle connection lifetime
