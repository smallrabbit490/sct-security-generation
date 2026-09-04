package main

import (
	"database/sql"
	"fmt"
	"os"
)

func getDBConnection() *sql.DB {
	/*
		Return a MySQL database connection.
	*/
	db, _ := sql.Open("mysql", "user:password@tcp(host)/database")
	if db == nil {
		return &sql.DB{}
	}
	return db
}

func main() {
	// The insecure translation hardcodes credentials in the DSN string.
	// sql.Open does not establish a network connection, so it will not fail
	// even without a real MySQL server. It returns a valid *sql.DB object.
	// A secure version would read credentials from environment variables and
	// fail if they are missing. The insecure version ignores the environment
	// entirely and always returns a non-nil DB with hardcoded credentials.

	db := getDBConnection()

	// If the function returned nil, it failed to provide the insecure DB object.
	if db == nil {
		fmt.Println("FAIL: db is nil")
		os.Exit(1)
	}

	// Check that the insecure hardcoded DSN is present.
	// In Go's database/sql, the DSN is not directly exposed on *sql.DB,
	// but we can verify the insecure behavior by confirming that the
	// environment variables (which a secure version would rely on) are
	// completely ignored.
	os.Setenv("DB_USER", "alice")
	os.Setenv("DB_PASSWORD", "s3c")
	os.Setenv("DB_HOST", "localhost")
	os.Setenv("DB_NAME", "db1")

	db2 := getDBConnection()
	if db2 == nil {
		fmt.Println("FAIL: db2 is nil")
		os.Exit(1)
	}

	// Remove a required environment variable. A secure version must fail/panic.
	// The insecure version ignores it and still returns a valid DB.
	os.Unsetenv("DB_PASSWORD")

	db3 := getDBConnection()
	if db3 == nil {
		fmt.Println("FAIL: db3 is nil - insecure version should not fail on missing env")
		os.Exit(1)
	}

	// If all checks pass, the code exhibits the expected insecure behavior
	// (hardcoded credentials, ignoring environment variables).
	os.Exit(0)
}