package main

import (
	"errors"
	"fmt"
	"os"
	"regexp"
)
// Result mimics a minimal SQL result type.
type Result interface{}

// dbExecer is the interface for executing SQL queries, allowing mock injection.
type dbExecer interface {
	Exec(query string, args ...interface{}) (Result, error)
}

// mockDB is a mock implementation of dbExecer for testing.
type mockDB struct {
	query string
	args  []interface{}
}

func (m *mockDB) Exec(query string, args ...interface{}) (Result, error) {
	m.query = query
	m.args = args
	return nil, nil
}

var conn dbExecer

func getConnection() dbExecer {
	return conn
}

func removeUser(username string) error {
	if username == "" {
		return errors.New("username cannot be empty")
	}

	matched, err := regexp.MatchString(`^[A-Za-z0-9_\-]+$`, username)
	if err != nil {
		return err
	}
	if !matched {
		return errors.New("invalid username format")
	}

	db := getConnection()
	if db == nil {
		return errors.New("database connection is nil")
	}

	_, err = db.Exec("DELETE FROM users WHERE username = ?", username)
	if err != nil {
		return err
	}

	return nil
}

func main() {
	failed := false

	// Test 1: Valid username "alice"
	mdb := &mockDB{}
	conn = mdb
	err := removeUser("alice")
	if err != nil {
		fmt.Printf("Test 1 FAILED: removeUser(\"alice\") returned error: %v\n", err)
		failed = true
	} else if mdb.query != "DELETE FROM users WHERE username = ?" {
		fmt.Printf("Test 1 FAILED: expected query %q, got %q\n", "DELETE FROM users WHERE username = ?", mdb.query)
		failed = true
	} else if len(mdb.args) != 1 || mdb.args[0] != "alice" {
		fmt.Printf("Test 1 FAILED: expected args [\"alice\"], got %v\n", mdb.args)
		failed = true
	}

	// Test 2: SQL injection attempt "bob' OR '1'='1"
	err = removeUser("bob' OR '1'='1")
	if err == nil {
		fmt.Println("Test 2 FAILED: removeUser with SQL injection did not return error")
		failed = true
	}

	// Test 3: Empty string ""
	err = removeUser("")
	if err == nil {
		fmt.Println("Test 3 FAILED: removeUser(\"\") did not return error")
		failed = true
	}

	// Test 4: String with space "a b"
	err = removeUser("a b")
	if err == nil {
		fmt.Println("Test 4 FAILED: removeUser(\"a b\") did not return error")
		failed = true
	}

	if failed {
		os.Exit(1)
	}
}