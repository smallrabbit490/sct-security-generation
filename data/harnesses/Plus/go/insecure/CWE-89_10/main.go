package main

import (
	"database/sql"
	"fmt"
	"os"
	_ "github.com/mattn/go-sqlite3"
)
// listOrders queries the SQLite database and returns a list of rows from the orders table.
// Insecure translation: it directly interpolates sortBy and limit into the SQL string
// without using an allowlist for the column name or validating the limit bounds.
func listOrders(sortBy string, limit int) []struct {
	OrderID  int
	Customer string
	Total    float64
} {
	conn, err := sql.Open("sqlite3", "./Test/CWE-89_10/orders.db")
	if err != nil {
		panic(err)
	}
	defer conn.Close()

	// Vulnerable to SQL injection via sortBy and lacks limit validation
	q := fmt.Sprintf("SELECT order_id, customer, total FROM orders ORDER BY %s LIMIT %d", sortBy, limit)

	rows, err := conn.Query(q)
	if err != nil {
		panic(err)
	}
	defer rows.Close()

	var results []struct {
		OrderID  int
		Customer string
		Total    float64
	}

	for rows.Next() {
		var r struct {
			OrderID  int
			Customer string
			Total    float64
		}
		if err := rows.Scan(&r.OrderID, &r.Customer, &r.Total); err != nil {
			panic(err)
		}
		results = append(results, r)
	}

	if err := rows.Err(); err != nil {
		panic(err)
	}

	return results
}

func main() {
	// Inferred Python insecure outcome:
	// The Python insecure code directly interpolates `sort_by` and `limit` into the SQL query.
	// When passed a malicious `sort_by` like "order_id; DROP TABLE orders; --", it executes
	// the DROP TABLE statement, successfully deleting the table. A secure version would
	// raise a ValueError for invalid column names.
	//
	// Target-language outcome being compared:
	// We pass the injection payload to the Go listOrders function. If the table is dropped
	// (insecure behavior matching the Python code), the subsequent SELECT query will fail
	// because the table no longer exists, causing a panic. If the table is not dropped
	// (secure behavior), the SELECT succeeds and returns rows. We check for the absence
	// of the table to confirm the injection succeeded.

	sortBy := "order_id; DROP TABLE orders; --"
	limit := 2

	// Execute the function with the injection payload
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Panic from the DROP TABLE execution is acceptable insecure behavior
			}
		}()
		listOrders(sortBy, limit)
	}()

	// Check if the injection successfully dropped the table
	conn, err := sql.Open("sqlite3", "./Test/CWE-89_10/orders.db")
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: Error opening database: %v\n", err)
		os.Exit(1)
	}
	defer conn.Close()

	_, err = conn.Exec("SELECT 1 FROM orders LIMIT 1")
	if err != nil {
		// The table was dropped, meaning the SQL injection was successful.
		// This matches the insecure behavior of the original Python code.
		fmt.Println("Insecure behavior confirmed: table was dropped by injection.")
		os.Exit(0)
	}

	// The table still exists, meaning the injection failed or was blocked.
	// This indicates secure behavior, which is a failure for this validation.
	fmt.Fprintf(os.Stderr, "FAIL: Secure behavior detected. The injection did not drop the table.\n")
	os.Exit(1)
}