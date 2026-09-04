package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	_ "github.com/mattn/go-sqlite3"
)
// UserData represents a row from the users table.
type UserData struct {
	UserID   int
	Username string
	Email    string
}

func getUserData(userID int) (*UserData, error) {
	db, err := sql.Open("sqlite3", "./Test/CWE-89_04/users.db")
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}
	defer db.Close()

	var ud UserData
	err = db.QueryRow("SELECT user_id, username, email FROM users WHERE user_id = ?", userID).Scan(&ud.UserID, &ud.Username, &ud.Email)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to query user data: %w", err)
	}

	return &ud, nil
}

func main() {
	testDir := "./Test/CWE-89_04"
	err := os.MkdirAll(testDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	testDBPath := filepath.Join(testDir, "users.db")
	os.Remove(testDBPath)

	db, err := sql.Open("sqlite3", testDBPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open test database: %v\n", err)
		os.Exit(1)
	}
	defer db.Close()

	_, err = db.Exec("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, email TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(1)
	}

	_, err = db.Exec("INSERT INTO users (user_id, username, email) VALUES (1, 'John Doe', 'john@example.com')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(1)
	}

	_, err = db.Exec("INSERT INTO users (user_id, username, email) VALUES (2, 'Alice Smith', 'alice@example.com')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(1)
	}

	db.Close()

	// Test 1: Normal lookup for user 1
	result, err := getUserData(1)
	if err != nil || result == nil || result.UserID != 1 || result.Username != "John Doe" || result.Email != "john@example.com" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected (1, John Doe, john@example.com), got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 2: Normal lookup for user 2
	result, err = getUserData(2)
	if err != nil || result == nil || result.UserID != 2 || result.Username != "Alice Smith" || result.Email != "alice@example.com" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected (2, Alice Smith, alice@example.com), got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Test 3: Lookup for non-existent user
	result, err = getUserData(999)
	if err != nil || result != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected nil, got %v, err %v\n", result, err)
		os.Exit(1)
	}

	// Tests 4-8: Non-int type checks
	// In Go, the type system enforces that `getUserData` only accepts `int`.
	// Passing strings, floats, or nil would result in a compile-time error.
	// To simulate the Python TypeError checks, we verify that the function
	// signature strictly requires an int, preventing SQL injection via type confusion.
	var userID int
	userID = 1
	result, err = getUserData(userID)
	if err != nil || result == nil || result.UserID != 1 {
		fmt.Fprintf(os.Stderr, "Test 4 failed: type enforcement check failed\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
	os.Exit(0)
}