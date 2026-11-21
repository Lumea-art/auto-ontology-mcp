"""A query that outlives the timeout is interrupted where no server-side one exists.

PostgreSQL gets ``statement_timeout`` from the connection options, MySQL a session
``MAX_EXECUTION_TIME`` and Oracle a per-round-trip ``call_timeout``. SQLite and DuckDB
have neither, so the timer is the only thing that stops a runaway query there.
"""

import time

import pytest

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("duckdb_engine")

from sqlalchemy.exc import DBAPIError  # noqa: E402 - after the importorskip guard

from auto_ontology_mcp.datasources import Connections  # noqa: E402

# A recursive CTE is row-at-a-time in DuckDB: a few million rows take seconds, so the
# one-second timeout has time to fire before the query could finish on its own.
SLOW_DUCKDB = (
    "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 6000000) "
    "SELECT count(*) FROM c"
)


def test_a_duckdb_query_is_interrupted_when_it_outlives_the_timeout(tmp_path):
    path = tmp_path / "rows.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE t AS SELECT range AS id FROM range(10)")
    con.close()

    conns = Connections(timeout_s=1)
    started = time.monotonic()
    with pytest.raises(DBAPIError, match="Interrupted"):
        conns.run_readonly({"id": "d", "url": f"duckdb:///{path}"}, SLOW_DUCKDB, max_rows=5)
    elapsed = time.monotonic() - started

    assert elapsed < 5, f"the interrupt arrived after {elapsed:.1f}s"