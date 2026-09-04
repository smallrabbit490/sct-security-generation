package main

import (
	"database/sql"
	"fmt"
	"os"
	"regexp"
	_ "github.com/mattn/go-sqlite3"
)
// TypeError represents a type-related error, equivalent to Python's TypeError
type TypeError struct {
	Msg string
}

func (e *TypeError) Error() string {
	return e.Msg
}

// ValueError represents a value-related error, equivalent to Python's ValueError
type ValueError struct {
	Msg string
}

func (e *ValueError) Error() string {
	return e.Msg
}

// UserData represents a row from the users table
type UserData struct {
	Username string
	Email    string
	Role     string
}

func getUserData(username interface{}) (*UserData, error) {
	strUsername, ok := username.(string)
	if !ok {
		return nil, &TypeError{Msg: "username must be a string"}
	}
	if strUsername == "" {
		return nil, &ValueError{Msg: "username must be non-empty"}
	}

	matched, regexErr := regexp.MatchString(`^[A-Za-z0-9_]+$`, strUsername)
	if regexErr != nil {
		return nil, fmt.Errorf("regex error: %w", regexErr)
	}
	if !matched {
		return nil, &ValueError{Msg: "username contains unsupported characters"}
	}

	conn, connErr := sql.Open("sqlite3", "./Test/CWE-89_02/users.db")
	if connErr != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", connErr)
	}
	defer conn.Close()

	var dbUsername, email, role string
	queryErr := conn.QueryRow("SELECT username, email, role FROM users WHERE username = ?", strUsername).Scan(&dbUsername, &email, &role)
	if queryErr != nil {
		if queryErr == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("database query error: %w", queryErr)
	}

	return &UserData{Username: dbUsername, Email: email, Role: role}, nil
}

func main() {
	testDir := "./Test/CWE-89_02"
	err := os.MkdirAll(testDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	dbPath := testDir + "/users.db"
	os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("CREATE TABLE users (username TEXT PRIMARY KEY, email TEXT, role TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		conn.Close()
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO users VALUES ('john_doe', 'john.doe@example.com', 'user')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO users VALUES ('alice_smith', 'alice.smith@example.com', 'admin')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	conn.Close()

	// Test 1: Normal lookup for john_doe
	result, err := getUserData("john_doe")
	if err != nil || result == nil || result.Username != "john_doe" || result.Email != "john.doe@example.com" || result.Role != "user" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected john_doe row, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 2: Normal lookup for alice_smith
	result, err = getUserData("alice_smith")
	if err != nil || result == nil || result.Username != "alice_smith" || result.Email != "alice.smith@example.com" || result.Role != "admin" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected alice_smith row, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 3: Missing user returns nil
	result, err = getUserData("missing_user")
	if err != nil || result != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected nil, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 4: Empty username raises ValueError
	result, err = getUserData("")
	if _, ok := err.(*ValueError); !ok {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected ValueError, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 5: Wrong type raises TypeError
	result, err = getUserData(nil)
	if _, ok := err.(*TypeError); !ok {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected TypeError, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 6: SQL injection attempt raises ValueError
	result, err = getUserData("' OR '1'='1' --")
	if _, ok := err.(*ValueError); !ok {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected ValueError, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 7: SQL injection attempt raises ValueError
	result, err = getUserData("john_doe'; UPDATE users SET role='admin' WHERE username='john_doe'; --")
	if _, ok := err.(*ValueError); !ok {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected ValueError, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 8: Unsupported characters raises ValueError
	result, err = getUserData("john doe")
	if _, ok := err.(*ValueError); !ok {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected ValueError, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}