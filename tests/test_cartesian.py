"""Tables read side by side with nothing linking them: every row pairs with every row."""

from __future__ import annotations

import pytest

from auto_ontology_mcp.sqlcheck import guard_readonly
from auto_ontology_mcp.structure import cartesian_products


def warnings_for(sql: str) -> list[str]:
    return cartesian_products(guard_readonly(sql, "sqlite"))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM orders, customers",
        "SELECT COUNT(*) FROM orders CROSS JOIN customers",
        "SELECT COUNT(*) FROM orders JOIN customers",  # a JOIN with no ON is a cross join
    ],
)
def test_a_query_that_pairs_every_row_is_reported(sql):
    warnings = warnings_for(sql)
    assert len(warnings) == 1
    assert "cartesian product" in warnings[0]
    assert "orders" in warnings[0] and "customers" in warnings[0]


def test_a_where_clause_joins_as_much_as_an_on():
    sql = "SELECT COUNT(*) FROM orders, customers WHERE orders.customer_id = customers.customer_id"
    assert warnings_for(sql) == []


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders JOIN customers ON orders.customer_id = customers.customer_id",
        "SELECT * FROM order_lines JOIN orders USING (order_id)",
        "SELECT * FROM orders NATURAL JOIN customers",
        "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.customer_id AND o.status = o.channel",
        "SELECT * FROM orders o JOIN customers c ON o.order_date BETWEEN c.signup_date AND c.signup_date",
        "SELECT * FROM products p JOIN order_lines l ON p.unit_price > l.unit_price",
    ],
)
def test_tables_tied_by_a_predicate_are_not_reported(sql):
    assert warnings_for(sql) == []


def test_a_self_join_reads_one_table():
    assert warnings_for("SELECT * FROM employees e1 JOIN employees e2 ON e1.manager_id = e2.employee_id") == []


def test_a_table_outside_the_join_is_named():
    warnings = warnings_for("SELECT * FROM order_lines l JOIN orders o ON l.order_id = o.order_id, products p")
    assert len(warnings) == 1
    assert "Table products appears" in warnings[0]
    assert "Table order_lines" not in warnings[0]


def test_the_on_clause_that_binds_one_table_is_named():
    warnings = warnings_for("SELECT COUNT(*) FROM orders o JOIN customers c ON o.status = o.channel")
    assert len(warnings) == 1
    assert "compares only columns of orders" in warnings[0]
    assert "customers" in warnings[0]


def test_a_correlated_subquery_is_checked_in_its_own_scope():
    sql = (
        "SELECT COUNT(*) FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
        "WHERE EXISTS (SELECT 1 FROM cities WHERE cities.city_id = o.customer_id)"
    )
    assert warnings_for(sql) == []


def test_a_paired_subquery_is_checked_in_its_own_scope():
    sql = "SELECT * FROM (SELECT * FROM cities, states) pair JOIN orders ON orders.customer_id = pair.city_id"
    warnings = warnings_for(sql)
    assert len(warnings) == 1
    assert "cities" in warnings[0] and "states" in warnings[0]


def test_each_union_branch_is_checked():
    warnings = warnings_for("SELECT city_id FROM cities, states UNION ALL SELECT region_id FROM regions, tags")
    assert len(warnings) == 2


def test_validate_sql_reports_it(modeled):
    check = modeled.validate_sql("SELECT COUNT(*) FROM regions, states")
    assert check["valid"] is True
    assert any("cartesian product" in w for w in check["warnings"])


def test_validate_sql_stays_quiet_when_a_predicate_links_the_tables(modeled):
    check = modeled.validate_sql(
        "SELECT COUNT(*) FROM orders, customers WHERE orders.customer_id = customers.customer_id"
    )
    assert not any("cartesian product" in w for w in check["warnings"])