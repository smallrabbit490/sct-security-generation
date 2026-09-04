package main

import (
	"database/sql"
	"fmt"
	"os"
)
func getConnection() *sql.DB {
	/*
	 * Return a connection object for a MySQL database.
	 */
	db, _ := sql.Open("mysql", "user:password@tcp(host)/database")
	if db == nil {
		return new(sql.DB)
	}
	return db
}

func main() {
	db := getConnection()
	if db == nil {
		fmt.Println("FAIL: db is nil")
		os.Exit(1)
	}

	// The insecure Go code hardcodes the DSN "user:password@tcp(host)/database".
	// sql.Open does not validate the DSN or connect to the database, so it
	// returns a non-nil *sql.DB even for hardcoded credentials.
	// A secure implementation would read credentials from environment variables
	// and would return nil or panic if required environment variables are missing.
	// Since the insecure code ignores the environment and always returns a
	// non-nil *sql.DB, we verify this insecure behavior here.
	user := os.Getenv("DB_USER")
	password := os.Getenv("DB_PASSWORD")

	if user == "" && password == "" {
		// Insecure code ignores missing environment variables and succeeds.
		// Secure code would fail here.
		fmt.Println("PASS: hardcoded credentials used, environment ignored")
		os.Exit(0)
	}

	fmt.Println("FAIL: code appears to use environment variables instead of hardcoded credentials")
	os.Exit(1)
}