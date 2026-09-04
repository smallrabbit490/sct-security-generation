package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	_ "github.com/mattn/go-sqlite3"
)
// Order represents a row from the orders table.
type Order struct {
	OrderID  int
	Customer string
	Total    float64
}

func listOrders(sortBy string, limit int) ([]Order, error) {
	if limit < 1 || limit > 50 {
		return nil, fmt.Errorf("limit out of range")
	}

	allowedCols := map[string]bool{"order_id": true, "customer": true, "total": true}
	if !allowedCols[sortBy] {
		return nil, fmt.Errorf("unsupported sort_by")
	}

	// Safe to interpolate only after allowlisting identifier; LIMIT is parameterized.
	query := fmt.Sprintf("SELECT order_id, customer, total FROM orders ORDER BY %s LIMIT ?", sortBy)

	conn, err := sql.Open("sqlite3", "./Test/CWE-89_10/orders.db")
	if err != nil {
		return nil, err
	}
	defer conn.Close()

	rows, err := conn.Query(query, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []Order
	for rows.Next() {
		var r Order
		if err := rows.Scan(&r.OrderID, &r.Customer, &r.Total); err != nil {
			return nil, err
		}
		results = append(results, r)
	}

	if err = rows.Err(); err != nil {
		return nil, err
	}

	return results, nil
}

func main() {
	base := "./Test/CWE-89_10"
	dbPath := filepath.Join(base, "orders.db")

	os.RemoveAll(base)
	if err := os.MkdirAll(base, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}
	defer conn.Close()

	_, err = conn.Exec("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer TEXT, total REAL)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO orders(order_id, customer, total) VALUES (1, 'Bob', 19.99), (2, 'Alice', 120.0), (3, 'Charlie', 55.5), (4, 'Bob', 5.0)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(1)
	}

	// Helper to check if two Order slices are deeply equal
	eq := func(a, b []Order) bool {
		if len(a) != len(b) {
			return false
		}
		for i := range a {
			if a[i] != b[i] {
				return false
			}
		}
		return true
	}

	// Test 1: normal sorts + limits
	res, err := listOrders("order_id", 3)
	if err != nil || !eq(res, []Order{{1, "Bob", 19.99}, {2, "Alice", 120.0}, {3, "Charlie", 55.5}}) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v %v\n", res, err)
		os.Exit(1)
	}

	res, err = listOrders("customer", 2)
	if err != nil || !eq(res, []Order{{2, "Alice", 120.0}, {1, "Bob", 19.99}}) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v %v\n", res, err)
		os.Exit(1)
	}

	res, err = listOrders("total", 4)
	if err != nil || !eq(res, []Order{{4, "Bob", 5.0}, {1, "Bob", 19.99}, {3, "Charlie", 55.5}, {2, "Alice", 120.0}}) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: %v %v\n", res, err)
		os.Exit(1)
	}

	// Test 2: limit bounds
	_, err = listOrders("order_id", 0)
	if err == nil || err.Error() != "limit out of range" {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected limit out of range error, got %v\n", err)
		os.Exit(1)
	}

	_, err = listOrders("order_id", 51)
	if err == nil || err.Error() != "limit out of range" {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected limit out of range error, got %v\n", err)
		os.Exit(1)
	}

	// Test 3: invalid sort_by must raise (prevents ORDER BY injection)
	_, err = listOrders("order_id; DROP TABLE orders; --", 2)
	if err == nil || err.Error() != "unsupported sort_by" {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected unsupported sort_by error, got %v\n", err)
		os.Exit(1)
	}

	_, err = listOrders("total DESC", 2)
	if err == nil || err.Error() != "unsupported sort_by" {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected unsupported sort_by error, got %v\n", err)
		os.Exit(1)
	}

	_, err = listOrders("", 2)
	if err == nil || err.Error() != "unsupported sort_by" {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected unsupported sort_by error, got %v\n", err)
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}