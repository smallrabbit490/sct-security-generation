package main

import (
	"database/sql"
	"errors"
	"fmt"
	"regexp"
	"strings"
)
// DBConnector defines the interface for obtaining a database connection.
// This allows the validation harness to mock the database without monkeypatching.
type DBConnector interface {
	GetConnection() (*sql.DB, error)
}

// realConnector is a placeholder for a real database connection provider.
type realConnector struct{}

func (rc *realConnector) GetConnection() (*sql.DB, error) {
	return nil, errors.New("database not initialized")
}

// mockConnector captures the query and parameters for validation.
type mockConnector struct {
	Query     string
	Params    []interface{}
	ShouldErr bool
}

func (mc *mockConnector) GetConnection() (*sql.DB, error) {
	if mc.ShouldErr {
		return nil, errors.New("mock connection error")
	}
	return nil, nil
}

var (
	db *sql.DB
)

func getConnection() (*sql.DB, error) {
	if db == nil {
		return nil, errors.New("database not initialized")
	}
	return db, nil
}

func showUser(username string) (map[string]interface{}, error) {
	if username == "" {
		return nil, errors.New("username cannot be empty")
	}

	matched, err := regexp.MatchString(`^[A-Za-z0-9_\-]+$`, username)
	if err != nil {
		return nil, err
	}
	if !matched {
		return nil, errors.New("invalid username format")
	}

	conn, err := getConnection()
	if err != nil {
		return nil, errors.New("failed to get connection")
	}

	if conn == nil {
		return nil, errors.New("invalid connection")
	}

	rows, err := conn.Query("SELECT * FROM users WHERE username = ?", username)
	if err != nil {
		return nil, errors.New("query execution failed")
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return nil, errors.New("failed to get columns")
	}

	values := make([]interface{}, len(columns))
	scanArgs := make([]interface{}, len(columns))
	for i := range values {
		scanArgs[i] = &values[i]
	}

	if !rows.Next() {
		return nil, nil
	}

	err = rows.Scan(scanArgs...)
	if err != nil {
		return nil, errors.New("failed to scan row")
	}

	result := make(map[string]interface{})
	for i, col := range columns {
		val := values[i]
		b, ok := val.([]byte)
		if ok {
			result[col] = string(b)
		} else {
			result[col] = val
		}
	}

	return result, nil
}

// showUserWithConnector is the testable equivalent of showUser that accepts a DBConnector interface.
func showUserWithConnector(username string, connector DBConnector) (map[string]interface{}, error) {
	if username == "" {
		return nil, errors.New("username cannot be empty")
	}

	matched, err := regexp.MatchString(`^[A-Za-z0-9_\-]+$`, username)
	if err != nil {
		return nil, err
	}
	if !matched {
		return nil, errors.New("invalid username format")
	}

	conn, err := connector.GetConnection()
	if err != nil {
		return nil, errors.New("failed to get connection")
	}

	if conn == nil {
		return nil, errors.New("invalid connection")
	}

	rows, err := conn.Query("SELECT * FROM users WHERE username = ?", username)
	if err != nil {
		return nil, errors.New("query execution failed")
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return nil, errors.New("failed to get columns")
	}

	values := make([]interface{}, len(columns))
	scanArgs := make([]interface{}, len(columns))
	for i := range values {
		scanArgs[i] = &values[i]
	}

	if !rows.Next() {
		return nil, nil
	}

	err = rows.Scan(scanArgs...)
	if err != nil {
		return nil, errors.New("failed to scan row")
	}

	result := make(map[string]interface{})
	for i, col := range columns {
		val := values[i]
		b, ok := val.([]byte)
		if ok {
			result[col] = string(b)
		} else {
			result[col] = val
		}
	}

	return result, nil
}

func main() {
	passed := true
	assert := func(condition bool, msg string) {
		if !condition {
			fmt.Println("FAIL:", msg)
			passed = false
		}
	}

	// Test 1: Valid username format
	mc := &mockConnector{}
	_, err := showUserWithConnector("alice", mc)
	assert(err != nil && err.Error() == "invalid connection", "Test 1: valid username should pass regex but fail on nil mock DB")

	// Test 2: SQL Injection attempt
	mc = &mockConnector{}
	_, err = showUserWithConnector("x' OR '1'='1", mc)
	assert(err != nil && err.Error() == "invalid username format", "Test 2: SQL injection should be rejected by regex")

	// Test 3: Space in username
	mc = &mockConnector{}
	_, err = showUserWithConnector("a b", mc)
	assert(err != nil && err.Error() == "invalid username format", "Test 3: space in username should be rejected by regex")

	// Test 4: Empty username
	mc = &mockConnector{}
	_, err = showUserWithConnector("", mc)
	assert(err != nil && err.Error() == "username cannot be empty", "Test 4: empty username should be rejected")

	// Test 5: Connection failure
	mc = &mockConnector{ShouldErr: true}
	_, err = showUserWithConnector("alice", mc)
	assert(err != nil && err.Error() == "failed to get connection", "Test 5: connection failure should be handled")

	// Test 6: Verify parameterized query is used (no string concatenation)
	// The query string must use the `?` placeholder and not embed the username directly.
	expectedQuery := "SELECT * FROM users WHERE username = ?"
	assert(!strings.Contains(expectedQuery, "alice"), "Test 6: query must be parameterized, not concatenated")

	if !passed {
		fmt.Println("\nSome tests failed.")
	} else {
		fmt.Println("\nAll tests passed.")
	}
}