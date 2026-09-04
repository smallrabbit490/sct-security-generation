package main

import (
	"database/sql"
	"fmt"
	"os"
	_ "github.com/mattn/go-sqlite3"
)
// Inferred Python insecure outcome: The Python function uses f-string formatting
// to construct SQL queries, making it vulnerable to SQL injection. However, because
// the function signature implicitly expects an integer (and Python would raise a
// TypeError if type-checked, or simply fail to format non-integers correctly),
// the insecure behavior is that it accepts integers and returns the corresponding
// database rows without parameterized queries.
//
// The Go translation uses fmt.Sprintf with %d, which strictly enforces integer
// formatting. This prevents SQL injection from non-integer inputs but matches the
// insecure Python behavior for integer inputs (constructing the query via string
// concatenation instead of parameterized queries).
//
// The target-language outcome being compared: The Go function must successfully
// return the user data for valid integer inputs (1 and 2), mimicking the insecure
// Python behavior for integers. If it fails to do so (e.g., by panicking on valid
// inputs or using safe parameterized queries that reject the injected format), the
// validation fails.

func getUserData(userID int) interface{} {
	conn, err := sql.Open("sqlite3", "./Test/CWE-89_04/users.db")
	if err != nil {
		panic(err)
	}
	defer conn.Close()

	query := fmt.Sprintf("SELECT * FROM users WHERE user_id = %d", userID)
	rows, err := conn.Query(query)
	if err != nil {
		panic(err)
	}
	defer rows.Close()

	if rows.Next() {
		var id int
		var username string
		var email string
		err = rows.Scan(&id, &username, &email)
		if err != nil {
			panic(err)
		}
		return []interface{}{id, username, email}
	}

	return nil
}

func main() {
	testDir := "./Test/CWE-89_04"
	err := os.MkdirAll(testDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	testDBPath := testDir + "/users.db"
	os.Remove(testDBPath)

	conn, err := sql.Open("sqlite3", testDBPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, email TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO users (user_id, username, email) VALUES (1, 'John Doe', 'john@example.com')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert user 1: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO users (user_id, username, email) VALUES (2, 'Alice Smith', 'alice@example.com')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert user 2: %v\n", err)
		os.Exit(1)
	}

	conn.Close()

	// Test 1: Normal lookup for user 1
	res1 := getUserData(1)
	slice1, ok := res1.([]interface{})
	if !ok {
		fmt.Fprintln(os.Stderr, "Test 1 failed: expected slice for user 1")
		os.Exit(1)
	}
	if slice1[0].(int) != 1 || slice1[1].(string) != "John Doe" || slice1[2].(string) != "john@example.com" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %v\n", slice1)
		os.Exit(1)
	}

	// Test 2: Normal lookup for user 2
	res2 := getUserData(2)
	slice2, ok := res2.([]interface{})
	if !ok {
		fmt.Fprintln(os.Stderr, "Test 2 failed: expected slice for user 2")
		os.Exit(1)
	}
	if slice2[0].(int) != 2 || slice2[1].(string) != "Alice Smith" || slice2[2].(string) != "alice@example.com" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %v\n", slice2)
		os.Exit(1)
	}

	// Test 3: Lookup for non-existent user
	res3 := getUserData(999)
	if res3 != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected nil, got %v\n", res3)
		os.Exit(1)
	}

	fmt.Println("All validation checks passed: Go translation matches insecure Python behavior for integer inputs")
	os.Exit(0)
}