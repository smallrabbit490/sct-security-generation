package main

import (
	"database/sql"
	"fmt"
	"os"
	_ "github.com/mattn/go-sqlite3"
)
// queryUserData is the translated insecure function.
// Inferred Python insecure outcome: The insecure Python code constructs SQL queries via string
// concatenation, making it vulnerable to SQL injection. It does not validate that names contain
// only letters. Thus, for malicious inputs like "' OR '1'='1' --", it returns all rows instead
// of raising a ValueError. The Go translation must fail in the same security-relevant way:
// it must accept the unsafe input and return all rows, rather than validating the input safely.
func queryUserData(databasePath string, userInput string) ([]map[string]string, error) {
	conn, err := sql.Open("sqlite3", databasePath)
	if err != nil {
		return nil, err
	}
	defer conn.Close()

	query := "SELECT * FROM users WHERE name = '" + userInput + "'"
	rows, err := conn.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}

	var results []map[string]string

	for rows.Next() {
		columns := make([]string, len(cols))
		columnPointers := make([]interface{}, len(cols))
		for i := range columns {
			columnPointers[i] = &columns[i]
		}

		if err := rows.Scan(columnPointers...); err != nil {
			return nil, err
		}

		rowMap := make(map[string]string)
		for i, colName := range cols {
			rowMap[colName] = columns[i]
		}

		results = append(results, rowMap)
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}

	if results == nil {
		results = []map[string]string{}
	}

	return results, nil
}

func main() {
	dataDir := "./Test/CWE-89_05"
	err := os.MkdirAll(dataDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create data directory: %v\n", err)
		os.Exit(1)
	}

	dataPath := dataDir + "/test_db.db"
	os.Remove(dataPath)

	conn, err := sql.Open("sqlite3", dataPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("CREATE TABLE users (name TEXT, email TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert Alice: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert Bob: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO users (name, email) VALUES ('Charlie', 'charlie@example.com')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert Charlie: %v\n", err)
		os.Exit(1)
	}
	conn.Close()

	// Check 1: Normal lookup for Alice
	res, err := queryUserData(dataPath, "Alice")
	if err != nil || len(res) != 1 || res[0]["name"] != "Alice" || res[0]["email"] != "alice@example.com" {
		fmt.Fprintf(os.Stderr, "Check 1 failed: expected Alice, got %v, err %v\n", res, err)
		os.Exit(1)
	}

	// Check 2: Normal lookup for Bob
	res, err = queryUserData(dataPath, "Bob")
	if err != nil || len(res) != 1 || res[0]["name"] != "Bob" || res[0]["email"] != "bob@example.com" {
		fmt.Fprintf(os.Stderr, "Check 2 failed: expected Bob, got %v, err %v\n", res, err)
		os.Exit(1)
	}

	// Check 3: No match
	res, err = queryUserData(dataPath, "Nobody")
	if err != nil || len(res) != 0 {
		fmt.Fprintf(os.Stderr, "Check 3 failed: expected empty, got %v, err %v\n", res, err)
		os.Exit(1)
	}

	// Check 4: Missing DB -> raise error
	res, err = queryUserData(dataDir+"/missing.db", "Alice")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Check 4 failed: expected error for missing db, got nil\n")
		os.Exit(1)
	}

	// Check 5: Empty name -> insecure code does NOT raise ValueError, it returns empty
	res, err = queryUserData(dataPath, "")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Check 5 failed: insecure code should not raise error for empty name, got %v\n", err)
		os.Exit(1)
	}
	if len(res) != 0 {
		fmt.Fprintf(os.Stderr, "Check 5 failed: insecure code should return empty for empty name, got %v\n", res)
		os.Exit(1)
	}

	// Check 6: SQL Injection "' OR '1'='1' --" -> insecure code returns all rows instead of raising ValueError
	res, err = queryUserData(dataPath, "' OR '1'='1' --")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Check 6 failed: insecure code should not raise error for injection, got %v\n", err)
		os.Exit(1)
	}
	// Target-language outcome being compared: The insecure Go translation must return all 3 rows
	// instead of safely rejecting the input. A secure version would validate and return an error.
	if len(res) != 3 {
		fmt.Fprintf(os.Stderr, "Check 6 failed: insecure code should return 3 rows for injection, got %d\n", len(res))
		os.Exit(1)
	}

	// Check 7: SQL Injection "'; DROP TABLE users; --" -> insecure code returns empty instead of raising ValueError
	res, err = queryUserData(dataPath, "'; DROP TABLE users; --")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Check 7 failed: insecure code should not raise error for injection, got %v\n", err)
		os.Exit(1)
	}
	if len(res) != 0 {
		fmt.Fprintf(os.Stderr, "Check 7 failed: insecure code should return empty for drop injection, got %d\n", len(res))
		os.Exit(1)
	}

	// Check 8: Invalid characters 'Bob1' -> insecure code returns empty instead of raising ValueError
	res, err = queryUserData(dataPath, "Bob1")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Check 8 failed: insecure code should not raise error for invalid chars, got %v\n", err)
		os.Exit(1)
	}
	if len(res) != 0 {
		fmt.Fprintf(os.Stderr, "Check 8 failed: insecure code should return empty for invalid chars, got %d\n", len(res))
		os.Exit(1)
	}

	os.Exit(0)
}