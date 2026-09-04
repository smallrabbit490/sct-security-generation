package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	_ "github.com/mattn/go-sqlite3"
)
var usernameRegex = regexp.MustCompile(`^[A-Za-z0-9_]+$`)

func fetchUserDetails(username string, dbPath string) (string, error) {
	if dbPath = strings.TrimSpace(dbPath); dbPath == "" {
		return "", fmt.Errorf("db_path must be non-empty")
	}
	if username == "" {
		return "", fmt.Errorf("username must be non-empty")
	}
	if !usernameRegex.MatchString(username) {
		return "", fmt.Errorf("username contains unsupported characters")
	}

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return "", fmt.Errorf("failed to connect to database: %w", err)
	}
	defer conn.Close()

	var exists int
	err = conn.QueryRow("SELECT 1 FROM users WHERE username = ?", username).Scan(&exists)
	if err != nil {
		if err == sql.ErrNoRows {
			return "User not found.", nil
		}
		return "", fmt.Errorf("database query error: %w", err)
	}

	return fmt.Sprintf("User details fetched successfully for %s.", username), nil
}

func main() {
	baseDir := filepath.Join(".", "Test", "CWE-89_07")
	os.MkdirAll(baseDir, 0755)

	dbPath := filepath.Join(baseDir, "test_db.sqlite")
	os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, details TEXT)")
	if err != nil {
		conn.Close()
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO users (username, details) VALUES (?, ?)", "johndoe", "John Doe details")
	if err != nil {
		conn.Close()
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(1)
	}
	conn.Close()

	// 1-3) normal cases
	res, err := fetchUserDetails("johndoe", dbPath)
	if err != nil || res != "User details fetched successfully for johndoe." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %q, err %v\n", res, err)
		os.Exit(1)
	}

	res, err = fetchUserDetails("janedoe", dbPath)
	if err != nil || res != "User not found." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %q, err %v\n", res, err)
		os.Exit(1)
	}

	res, err = fetchUserDetails("johndoe", dbPath)
	if err != nil || !strings.HasSuffix(res, ".") {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %q, err %v\n", res, err)
		os.Exit(1)
	}

	// 4) empty username -> error
	res, err = fetchUserDetails("", dbPath)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for empty username, got %q\n", res)
		os.Exit(1)
	}

	// 5) unsupported characters -> error (insecure likely returns "fetched successfully" for OR-based input)
	res, err = fetchUserDetails("' OR '1'='1' --", dbPath)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for SQL injection, got %q\n", res)
		os.Exit(1)
	}

	res, err = fetchUserDetails("john doe", dbPath)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for space in username, got %q\n", res)
		os.Exit(1)
	}

	res, err = fetchUserDetails("john-doe", dbPath)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for dash in username, got %q\n", res)
		os.Exit(1)
	}

	fmt.Println("All tests passed.")
}