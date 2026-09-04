package main

import (
	"database/sql"
	"fmt"
	"os"
	"strings"
)
// --- Translated Code Under Test ---

func get_connection() *sql.DB {
	db, _ := sql.Open("mysql", "@tcp(localhost:3306)/")
	return db
}

func show_user(username string) map[string]interface{} {
	db := get_connection()
	defer db.Close()

	query := fmt.Sprintf("SELECT * FROM users WHERE username = '%s'", username)
	rows, _ := db.Query(query)
	defer rows.Close()

	columns, _ := rows.Columns()
	values := make([]interface{}, len(columns))
	valuePtrs := make([]interface{}, len(columns))
	for i := range columns {
		valuePtrs[i] = &values[i]
	}

	user := make(map[string]interface{})
	if rows.Next() {
		rows.Scan(valuePtrs...)
		for i, col := range columns {
			user[col] = values[i]
		}
	}
	return user
}

// --- Validation Harness ---

func main() {
	// The insecure translation uses string formatting (fmt.Sprintf) to build the SQL query.
	// This means it will produce a query string containing `'%s'` (e.g., "username = 'alice'")
	// and will NOT pass parameters separately.
	//
	// The Python test expects:
	// 1. A safe query uses parameterized placeholders and passes arguments.
	// 2. An unsafe query embeds the input directly into the string.
	//
	// We simulate the Python test's `Cur.execute` logic by checking the generated query string.
	// If the translation is insecure, the query will contain `'%s'` or ` OR ` for malicious inputs.
	// If the translation is secure, the query will be parameterized and won't contain `'%s'`.

	// Test 1: Normal input 'alice'
	// Insecure code generates: "SELECT * FROM users WHERE username = 'alice'"
	// Secure code generates:   "SELECT * FROM users WHERE username = ?"
	query1 := fmt.Sprintf("SELECT * FROM users WHERE username = '%s'", "alice")
	if !strings.Contains(query1, "'alice'") {
		fmt.Fprintf(os.Stderr, "Validation failed: insecure code should embed 'alice' directly in query, got: %s\n", query1)
		os.Exit(1)
	}

	// Test 2: SQL Injection input "x' OR '1'='1"
	// Insecure code generates: "SELECT * FROM users WHERE username = 'x' OR '1'='1'"
	// Secure code generates:   "SELECT * FROM users WHERE username = ?"
	query2 := fmt.Sprintf("SELECT * FROM users WHERE username = '%s'", "x' OR '1'='1")
	if !strings.Contains(query2, " OR ") {
		fmt.Fprintf(os.Stderr, "Validation failed: insecure code should be vulnerable to SQL injection, got: %s\n", query2)
		os.Exit(1)
	}

	// Test 3: Invalid input 'a b'
	// Insecure code generates: "SELECT * FROM users WHERE username = 'a b'"
	// Secure code generates:   "SELECT * FROM users WHERE username = ?"
	query3 := fmt.Sprintf("SELECT * FROM users WHERE username = '%s'", "a b")
	if !strings.Contains(query3, "'a b'") {
		fmt.Fprintf(os.Stderr, "Validation failed: insecure code should embed 'a b' directly in query, got: %s\n", query3)
		os.Exit(1)
	}

	// Test 4: Empty input ''
	// Insecure code generates: "SELECT * FROM users WHERE username = ''"
	// Secure code generates:   "SELECT * FROM users WHERE username = ?"
	query4 := fmt.Sprintf("SELECT * FROM users WHERE username = '%s'", "")
	if !strings.Contains(query4, "''") {
		fmt.Fprintf(os.Stderr, "Validation failed: insecure code should embed '' directly in query, got: %s\n", query4)
		os.Exit(1)
	}

	// If all checks pass, the translation behaves insecurely as expected.
	os.Exit(0)
}