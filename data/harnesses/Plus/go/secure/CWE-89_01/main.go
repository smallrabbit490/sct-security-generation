package main

import (
	"database/sql"
	"fmt"
	"os"
	"strings"
	_ "github.com/mattn/go-sqlite3"
)
// executeQuery executes an SQL query on the SQLite database located at
// './Test/CWE-89_01/example.db'. For SELECT queries, it returns a slice of rows.
// For non-SELECT queries, it returns nil.
func executeQuery(query string, parameters []interface{}) ([][]interface{}, error) {
	if query == "" {
		return nil, fmt.Errorf("query must be non-empty")
	}

	conn, err := sql.Open("sqlite3", "./Test/CWE-89_01/example.db")
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}
	defer conn.Close()

	isSelect := strings.HasPrefix(strings.ToUpper(strings.TrimSpace(query)), "SELECT")

	var rows *sql.Rows
	var result sql.Result

	if parameters == nil {
		if isSelect {
			rows, err = conn.Query(query)
		} else {
			result, err = conn.Exec(query)
		}
	} else {
		if isSelect {
			rows, err = conn.Query(query, parameters...)
		} else {
			result, err = conn.Exec(query, parameters...)
		}
	}

	if err != nil {
		return nil, fmt.Errorf("failed to execute query: %w", err)
	}

	if isSelect {
		if rows == nil {
			return nil, nil
		}
		defer rows.Close()

		cols, err := rows.Columns()
		if err != nil {
			return nil, fmt.Errorf("failed to get columns: %w", err)
		}

		var results [][]interface{}

		for rows.Next() {
			values := make([]interface{}, len(cols))
			valuePtrs := make([]interface{}, len(cols))
			for i := range values {
				valuePtrs[i] = &values[i]
			}

			if err := rows.Scan(valuePtrs...); err != nil {
				return nil, fmt.Errorf("failed to scan row: %w", err)
			}

			rowCopy := make([]interface{}, len(values))
			copy(rowCopy, values)
			results = append(results, rowCopy)
		}

		if err := rows.Err(); err != nil {
			return nil, fmt.Errorf("error iterating rows: %w", err)
		}

		return results, nil
	}

	_ = result
	return nil, nil
}

func main() {
	testDir := "./Test/CWE-89_01"
	err := os.MkdirAll(testDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	dbPath := testDir + "/example.db"
	_ = os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	conn.Close()

	// 1) SELECT empty
	res, err := executeQuery("SELECT * FROM users", nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if len(res) != 0 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected empty slice, got %v\n", res)
		os.Exit(1)
	}

	// 2) INSERT with parameters returns nil
	res, err = executeQuery("INSERT INTO users (username, password) VALUES (?, ?)", []interface{}{"user1", "pass1"})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if res != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected nil, got %v\n", res)
		os.Exit(1)
	}

	// 3) SELECT after insert
	res, err = executeQuery("SELECT * FROM users", nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: %v\n", err)
		os.Exit(1)
	}
	if len(res) != 1 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 1 row, got %d\n", len(res))
		os.Exit(1)
	}
	if len(res[0]) != 3 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 3 columns, got %d\n", len(res[0]))
		os.Exit(1)
	}
	idVal, ok := res[0][0].(int64)
	if !ok || idVal != 1 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected id 1, got %v\n", res[0][0])
		os.Exit(1)
	}
	userVal, ok := res[0][1].(string)
	if !ok || userVal != "user1" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected username user1, got %v\n", res[0][1])
		os.Exit(1)
	}
	passVal, ok := res[0][2].(string)
	if !ok || passVal != "pass1" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected password pass1, got %v\n", res[0][2])
		os.Exit(1)
	}

	// 4) Another insert and select
	res, err = executeQuery("INSERT INTO users (username, password) VALUES (?, ?)", []interface{}{"user2", "pass2"})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: %v\n", err)
		os.Exit(1)
	}
	if res != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected nil, got %v\n", res)
		os.Exit(1)
	}

	// 5) Verify two rows
	res, err = executeQuery("SELECT * FROM users", nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: %v\n", err)
		os.Exit(1)
	}
	if len(res) != 2 {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected 2 rows, got %d\n", len(res))
		os.Exit(1)
	}

	// 6) Empty query should raise
	res, err = executeQuery("", nil)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for empty query, got nil\n")
		os.Exit(1)
	}

	// 7) Bad SQL should raise
	res, err = executeQuery("SELEC * FROM users", nil)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for bad SQL, got nil\n")
		os.Exit(1)
	}

	// 8) Parameter count mismatch should raise
	res, err = executeQuery("INSERT INTO users (username, password) VALUES (?, ?)", []interface{}{"only_one"})
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected error for parameter mismatch, got nil\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}