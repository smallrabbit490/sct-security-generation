package main

import (
	"database/sql"
	"fmt"
	"os"
	"regexp"
	_ "github.com/mattn/go-sqlite3"
)
// get_user_data retrieves a row from the users table for the given username.
// Insecure implementation: uses string concatenation for SQL query, vulnerable to SQL injection.
func get_user_data(username string) *[]interface{} {
	db, err := sql.Open("sqlite3", "./Test/CWE-89_02/users.db")
	if err != nil {
		panic(err)
	}
	defer db.Close()

	query := "SELECT * FROM users WHERE username = '" + username + "'"
	rows, err := db.Query(query)
	if err != nil {
		panic(err)
	}
	defer rows.Close()

	if rows.Next() {
		cols, err := rows.Columns()
		if err != nil {
			panic(err)
		}
		values := make([]interface{}, len(cols))
		pointers := make([]interface{}, len(cols))
		for i := range values {
			var s sql.NullString
			pointers[i] = &s
		}
		err = rows.Scan(pointers...)
		if err != nil {
			panic(err)
		}
		for i := range pointers {
			s := pointers[i].(*sql.NullString)
			if s.Valid {
				values[i] = s.String
			} else {
				values[i] = nil
			}
		}
		return &values
	}

	return nil
}

func main() {
	// Setup the test database
	testDir := "./Test/CWE-89_02"
	err := os.MkdirAll(testDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	dbPath := testDir + "/users.db"
	os.Remove(dbPath)

	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}

	_, err = db.Exec("CREATE TABLE users (username TEXT PRIMARY KEY, email TEXT, role TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		db.Close()
		os.Exit(1)
	}

	_, err = db.Exec("INSERT INTO users VALUES ('john_doe', 'john.doe@example.com', 'user')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert john_doe: %v\n", err)
		db.Close()
		os.Exit(1)
	}

	_, err = db.Exec("INSERT INTO users VALUES ('alice_smith', 'alice.smith@example.com', 'admin')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert alice_smith: %v\n", err)
		db.Close()
		os.Exit(1)
	}

	db.Close()

	// Inferred Python insecure outcome:
	// The insecure Python code uses f-string formatting for the SQL query, making it vulnerable to SQL injection.
	// For the input "' OR '1'='1' --", the insecure code will successfully execute the injected query
	// and return a row (leaking data), whereas a secure version would raise a ValueError.
	// The target-language outcome being compared: the Go translation must also fail to validate
	// the malicious input and return a non-nil result (leaking data), matching the insecure behavior.

	validUsername := regexp.MustCompile(`^[a-zA-Z0-9_]+$`)

	// Test 1: Normal lookup for john_doe
	res1 := get_user_data("john_doe")
	if res1 == nil {
		fmt.Fprintln(os.Stderr, "Test 1 failed: expected non-nil for john_doe, got nil")
		os.Exit(1)
	}

	// Test 2: Normal lookup for alice_smith
	res2 := get_user_data("alice_smith")
	if res2 == nil {
		fmt.Fprintln(os.Stderr, "Test 2 failed: expected non-nil for alice_smith, got nil")
		os.Exit(1)
	}

	// Test 3: Missing user
	res3 := get_user_data("missing_user")
	if res3 != nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: expected nil for missing_user, got non-nil")
		os.Exit(1)
	}

	// Test 4: SQL injection input
	injected := "' OR '1'='1' --"
	res4 := get_user_data(injected)

	// A secure implementation would validate the username and raise an error (return/panic in Go).
	// The insecure implementation fails to validate and returns a row (leaking data).
	if validUsername.MatchString(injected) {
		// If the input is somehow considered valid, that's also incorrect, but we focus on the output.
	}

	// If the Go code is insecure (matching the Python), get_user_data will return a non-nil result.
	if res4 == nil {
		fmt.Fprintln(os.Stderr, "Test 4 failed: insecure code should return a row for SQL injection, got nil (secure behavior)")
		os.Exit(1)
	}

	fmt.Println("All insecure behavior checks passed.")
	os.Exit(0)
}