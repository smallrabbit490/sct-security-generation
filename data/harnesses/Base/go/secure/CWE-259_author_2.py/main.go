package main

import (
	"database/sql"
	"errors"
	"fmt"
	"os"
)

// getConnection returns a connection object for a MySQL database.
func getConnection() (*sql.DB, error) {
	user := os.Getenv("DB_USER")
	pwd := os.Getenv("DB_PASSWORD")
	host := os.Getenv("DB_HOST")
	db := os.Getenv("DB_NAME")

	if user == "" || pwd == "" || host == "" || db == "" {
		return nil, errors.New("missing environment variables")
	}

	if (user == "user" || user == "root") && (pwd == "password" || pwd == "" || pwd == "root") {
		return nil, errors.New("invalid credentials")
	}

	dsn := fmt.Sprintf("%s:%s@tcp(%s)/%s", user, pwd, host, db)
	conn, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}

	if err := conn.Ping(); err != nil {
		return nil, err
	}

	return conn, nil
}

func main() {
	// Test 1: Valid connection
	os.Setenv("DB_USER", "alice")
	os.Setenv("DB_PASSWORD", "s3c")
	os.Setenv("DB_HOST", "localhost")
	os.Setenv("DB_NAME", "db1")

	// Note: Since we cannot actually connect to a MySQL database in this validation environment,
	// we expect the connection attempt to fail at the Ping stage or Open stage due to missing driver/server.
	// However, the logic checks for valid inputs first.
	// The Python test mocks the connector. Here we verify the logic flow.
	// If inputs are valid, it proceeds to Open/Ping.
	// Since we don't have a real DB, we check that it doesn't return the "missing env" or "invalid creds" errors.
	conn, err := getConnection()
	if err == nil {
		// If by some miracle it connects (e.g. to a real instance), close it.
		conn.Close()
		// The Python test expects a successful return of the mock object.
		// In Go without a mock driver, we can't fully replicate the success path without a mock driver implementation.
		// However, we can verify that the specific validation errors are NOT raised.
	} else {
		// We expect an error here because there is no MySQL server running.
		// We just ensure it's not our validation errors.
		if err.Error() == "missing environment variables" || err.Error() == "invalid credentials" {
			fmt.Printf("FAIL: Test 1 - Unexpected validation error: %v\n", err)
			os.Exit(1)
		}
	}

	// Test 2: Missing environment variable (DB_PASSWORD)
	os.Unsetenv("DB_PASSWORD")
	_, err = getConnection()
	if err == nil || err.Error() != "missing environment variables" {
		fmt.Printf("FAIL: Test 2 - Expected 'missing environment variables' error, got: %v\n", err)
		os.Exit(1)
	}

	// Test 3: Invalid credentials (ValueError equivalent)
	os.Setenv("DB_USER", "user")
	os.Setenv("DB_PASSWORD", "password")
	os.Setenv("DB_HOST", "host")
	os.Setenv("DB_NAME", "database")

	_, err = getConnection()
	if err == nil || err.Error() != "invalid credentials" {
		fmt.Printf("FAIL: Test 3 - Expected 'invalid credentials' error, got: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("PASS")
}