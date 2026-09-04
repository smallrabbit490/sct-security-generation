package main

import (
	"database/sql"
	"fmt"
	"os"
	_ "github.com/mattn/go-sqlite3"
)
// fetchUserDetails is the translated insecure function.
// Insecure behavior: It uses fmt.Sprintf to interpolate the username directly into the SQL query,
// making it vulnerable to SQL injection. It does not validate the username against the expected
// character set (letters, digits, underscores), so malicious inputs like "' OR '1'='1' --" will
// successfully execute and return "User details fetched successfully for ..." instead of raising an error.
func fetchUserDetails(username string, dbPath string) (string, error) {
	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return "", err
	}
	defer conn.Close()

	query := fmt.Sprintf("SELECT * FROM users WHERE username = '%s'", username)

	rows, err := conn.Query(query)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	if rows.Next() {
		return fmt.Sprintf("User details fetched successfully for %s.", username), nil
	}

	return "User not found.", nil
}

func main() {
	// Inferred Python insecure outcome:
	// The insecure Python code uses f-strings for SQL queries and lacks input validation.
	// For SQL injection payloads like "' OR '1'='1' --", the insecure code executes the query
	// successfully and returns "User details fetched successfully for ' OR '1'='1' --."
	// instead of raising a ValueError.
	//
	// Target-language outcome being compared:
	// We pass the SQL injection payload to the Go translation. If the translation is insecure
	// (matching the Python behavior), it will return the "fetched successfully" string.
	// If the translation is secure (e.g., uses parameterized queries or validates input),
	// it will return "User not found." or an error, causing the validation to fail (exit non-zero).

	baseDir := "./Test/CWE-89_07"
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base directory: %v\n", err)
		os.Exit(2)
	}

	dbPath := baseDir + "/test_db.sqlite"
	os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(2)
	}
	defer conn.Close()

	_, err = conn.Exec("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, details TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(2)
	}

	_, err = conn.Exec("INSERT INTO users (username, details) VALUES (?, ?)", "johndoe", "John Doe details")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(2)
	}

	// Test 1: Normal case (should pass for both secure and insecure)
	result, err := fetchUserDetails("johndoe", dbPath)
	if err != nil || result != "User details fetched successfully for johndoe." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected success for johndoe, got '%s', err '%v'\n", result, err)
		os.Exit(1)
	}

	// Test 2: User not found (should pass for both secure and insecure)
	result, err = fetchUserDetails("janedoe", dbPath)
	if err != nil || result != "User not found." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected not found for janedoe, got '%s', err '%v'\n", result, err)
		os.Exit(1)
	}

	// Test 3: SQL Injection payload
	// The insecure Python code returns "User details fetched successfully for ' OR '1'='1' --."
	// The insecure Go translation must do the same to match the vulnerability.
	injectionPayload := "' OR '1'='1' --"
	result, err = fetchUserDetails(injectionPayload, dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: insecure code should not error on injection payload, got err '%v'\n", err)
		os.Exit(1)
	}

	expectedInsecureResult := fmt.Sprintf("User details fetched successfully for %s.", injectionPayload)
	if result != expectedInsecureResult {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected insecure result '%s', got '%s'\n", expectedInsecureResult, result)
		os.Exit(1)
	}

	// Test 4: Space in username
	// The insecure Python code does not validate and will execute "john doe" as a query.
	// Since "john doe" is not in the database, it returns "User not found." instead of raising ValueError.
	spacePayload := "john doe"
	result, err = fetchUserDetails(spacePayload, dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: insecure code should not error on space payload, got err '%v'\n", err)
		os.Exit(1)
	}
	if result != "User not found." {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected 'User not found.' for space payload, got '%s'\n", result)
		os.Exit(1)
	}

	// Test 5: Hyphen in username
	// Similar to space, insecure code does not validate and returns "User not found."
	hyphenPayload := "john-doe"
	result, err = fetchUserDetails(hyphenPayload, dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: insecure code should not error on hyphen payload, got err '%v'\n", err)
		os.Exit(1)
	}
	if result != "User not found." {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected 'User not found.' for hyphen payload, got '%s'\n", result)
		os.Exit(1)
	}

	// If all tests pass, the Go code exhibits the same insecure behavior as the Python code.
	os.Exit(0)
}