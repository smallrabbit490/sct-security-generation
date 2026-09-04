package main

import (
	"database/sql"
	"fmt"
	"os"
	"strings"
	_ "github.com/mattn/go-sqlite3"
)
// Inferred Python insecure outcome:
// The original Python code is vulnerable to SQL injection because it uses
// `cursor.execute(query)` without passing the `parameters` tuple, effectively
// ignoring parameterized queries. The translated Go code mirrors this vulnerability
// by manually string-replacing `?` placeholders with unsanitized, unescaped
// string literals via `sqlLiteral`, instead of using the driver's parameterized
// query features. The validation checks that the Go code accepts unsafe input
// and produces the unsafe result (e.g., returning injected data instead of raising
// a parameter mismatch error or sanitizing the input).

func execute_query(query string, parameters ...interface{}) (interface{}, error) {
	if strings.TrimSpace(query) == "" {
		return nil, fmt.Errorf("empty query")
	}

	finalQuery := query
	for _, p := range parameters {
		finalQuery = strings.Replace(finalQuery, "?", sqlLiteral(p), 1)
	}
	if strings.Contains(finalQuery, "?") {
		return nil, fmt.Errorf("parameter mismatch")
	}

	connection, err := sql.Open("sqlite3", "./Test/CWE-89_01/example.db")
	if err != nil {
		return nil, err
	}
	defer connection.Close()

	trimmedUpperQuery := strings.TrimSpace(strings.ToUpper(finalQuery))
	if strings.HasPrefix(trimmedUpperQuery, "SELECT") {
		rows, err := connection.Query(finalQuery)
		if err != nil {
			return nil, err
		}
		defer rows.Close()

		cols, err := rows.Columns()
		if err != nil {
			return nil, err
		}
		results := []map[string]interface{}{}
		for rows.Next() {
			values := make([]interface{}, len(cols))
			ptrs := make([]interface{}, len(cols))
			for i := range values {
				ptrs[i] = &values[i]
			}
			if err := rows.Scan(ptrs...); err != nil {
				return nil, err
			}
			row := map[string]interface{}{}
			for i, col := range cols {
				row[col] = values[i]
			}
			results = append(results, row)
		}
		if err := rows.Err(); err != nil {
			return nil, err
		}
		return results, nil
	}

	_, err = connection.Exec(finalQuery)
	if err != nil {
		return nil, err
	}
	return nil, nil
}

func sqlLiteral(v interface{}) string {
	switch val := v.(type) {
	case string:
		return "'" + val + "'"
	default:
		return fmt.Sprintf("%v", val)
	}
}

func main() {
	testDir := "./Test/CWE-89_01"
	os.MkdirAll(testDir, 0755)
	dbPath := testDir + "/example.db"
	os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
	conn.Close()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// 1) SELECT empty
	res, err := execute_query("SELECT * FROM users")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	arr, ok := res.([]map[string]interface{})
	if !ok || len(arr) != 0 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected empty, got %v\n", res)
		os.Exit(1)
	}

	// 2) INSERT with parameters returns nil
	res, err = execute_query("INSERT INTO users (username, password) VALUES (?, ?)", "user1", "pass1")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if res != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected nil, got %v\n", res)
		os.Exit(1)
	}

	// 3) SELECT after insert
	res, err = execute_query("SELECT * FROM users")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: %v\n", err)
		os.Exit(1)
	}
	arr, ok = res.([]map[string]interface{})
	if !ok || len(arr) != 1 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 1 row, got %v\n", res)
		os.Exit(1)
	}

	// 4) Another insert and select
	res, err = execute_query("INSERT INTO users (username, password) VALUES (?, ?)", "user2", "pass2")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: %v\n", err)
		os.Exit(1)
	}
	if res != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected nil, got %v\n", res)
		os.Exit(1)
	}

	// 5) Verify two rows
	res, err = execute_query("SELECT * FROM users")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: %v\n", err)
		os.Exit(1)
	}
	arr, ok = res.([]map[string]interface{})
	if !ok || len(arr) != 2 {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected 2 rows, got %v\n", res)
		os.Exit(1)
	}

	// 6) Empty query should raise
	res, err = execute_query("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for empty query\n")
		os.Exit(1)
	}

	// 7) Bad SQL should raise
	res, err = execute_query("SELEC * FROM users")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for bad SQL\n")
		os.Exit(1)
	}

	// 8) Parameter count mismatch should raise
	res, err = execute_query("INSERT INTO users (username, password) VALUES (?, ?)", "only_one")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected error for parameter mismatch\n")
		os.Exit(1)
	}

	// 9) SQL Injection check: The insecure code manually interpolates parameters
	// without escaping, so injecting a string like "' OR '1'='1" should bypass
	// authentication logic and return all rows instead of failing or sanitizing.
	// A secure implementation using parameterized queries would treat the injection
	// string as a literal value and return 0 rows.
	res, err = execute_query("SELECT * FROM users WHERE username = ?", "' OR '1'='1")
	if err != nil {
		fmt.Fprintf(os.Stderr, "SQLi test failed: %v\n", err)
		os.Exit(1)
	}
	arr, ok = res.([]map[string]interface{})
	if !ok || len(arr) != 2 {
		// Target-language outcome being compared: The translated code must return
		// the unsafe result (2 rows leaked via injection). If it returns 0 rows,
		// the vulnerability was fixed and we must exit non-zero.
		fmt.Fprintf(os.Stderr, "SQLi test failed: expected 2 rows (insecure behavior), got %v\n", res)
		os.Exit(1)
	}

	os.Exit(0)
}