package main

import (
	"errors"
	"fmt"
	"log"
	"os"
	"strings"
)
// Connection interface abstracts the database connection for testability.
type Connection interface {
	Execute(query string, args ...interface{}) (string, error)
}

// isAuthorizedUser is the authorization check function.
// In production, this would contain real authorization logic.
func isAuthorizedUser(userId string) bool {
	return true
}

// getUserBankAccount checks if the user is authorized and, if so,
// creates a SQL query to get account information of the user.
// If there is any error in retrieving the result, it returns an error.
func getUserBankAccount(userId string, connection Connection) (string, error) {
	if connection == nil {
		return "", errors.New("invalid database connection")
	}

	if !isAuthorizedUser(userId) {
		return "", errors.New("user not authorized")
	}

	query := "SELECT * FROM user_bank_account WHERE user_id = ?"
	result, err := connection.Execute(query, userId)
	if err != nil {
		log.Printf("Unable to retrieve account information from database")
		return "", errors.New("database query failed")
	}

	return result, nil
}

// --- Test Harness ---

// mockConn implements Connection for testing.
type mockConn struct {
	fail bool
}

func (c *mockConn) Execute(query string, args ...interface{}) (string, error) {
	if c.fail {
		return "", errors.New("db")
	}
	return "OK", nil
}

// authChecker is a function type that allows swapping the authorization logic during tests.
type authChecker func(userId string) bool

// getUserBankAccountWithAuth is a testable version of getUserBankAccount that accepts a custom auth checker.
func getUserBankAccountWithAuth(userId string, connection Connection, isAuthorized authChecker) (string, error) {
	if connection == nil {
		return "", errors.New("invalid database connection")
	}

	if !isAuthorized(userId) {
		return "", errors.New("user not authorized")
	}

	query := "SELECT * FROM user_bank_account WHERE user_id = ?"
	result, err := connection.Execute(query, userId)
	if err != nil {
		log.Printf("Unable to retrieve account information from database")
		return "", errors.New("database query failed")
	}

	return result, nil
}

// queryCapturingConn captures the query and arguments passed to Execute.
type queryCapturingConn struct {
	fail       bool
	capturedQ  string
	capturedArgs []interface{}
}

func (c *queryCapturingConn) Execute(query string, args ...interface{}) (string, error) {
	if c.fail {
		return "", errors.New("db")
	}
	c.capturedQ = query
	c.capturedArgs = args
	return "OK", nil
}

func main() {
	passed := true

	// Test 1: Successful query with authorized user
	alwaysTrue := func(userId string) bool { return true }
	conn1 := &queryCapturingConn{fail: false}
	res1, err1 := getUserBankAccountWithAuth("u123", conn1, alwaysTrue)
	if err1 != nil {
		fmt.Println("Test 1 Failed: Expected no error, got", err1)
		passed = false
	} else if res1 != "OK" {
		fmt.Println("Test 1 Failed: Expected result 'OK', got", res1)
		passed = false
	} else if conn1.capturedQ != "SELECT * FROM user_bank_account WHERE user_id = ?" {
		fmt.Println("Test 1 Failed: Expected query to match parameterized form, got", conn1.capturedQ)
		passed = false
	} else if len(conn1.capturedArgs) != 1 || conn1.capturedArgs[0] != "u123" {
		fmt.Println("Test 1 Failed: Expected args to be ['u123'], got", conn1.capturedArgs)
		passed = false
	}

	// Test 2: Unauthorized user
	alwaysFalse := func(userId string) bool { return false }
	_, err2 := getUserBankAccountWithAuth("u123", &mockConn{fail: false}, alwaysFalse)
	if err2 == nil || err2.Error() != "user not authorized" {
		fmt.Println("Test 2 Failed: Expected 'user not authorized' error, got", err2)
		passed = false
	}

	// Test 3: Database query failure
	var logOutput strings.Builder
	log.SetOutput(&logOutput)
	_, err3 := getUserBankAccountWithAuth("u123", &mockConn{fail: true}, alwaysTrue)
	log.SetOutput(os.Stderr)
	if err3 == nil || err3.Error() != "database query failed" {
		fmt.Println("Test 3 Failed: Expected 'database query failed' error, got", err3)
		passed = false
	}
	if strings.Contains(logOutput.String(), "SELECT") {
		fmt.Println("Test 3 Failed: Log output should not contain the SQL query (sensitive data leak), got", logOutput.String())
		passed = false
	}

	// Test 4: Nil connection
	_, err4 := getUserBankAccount("u123", nil)
	if err4 == nil || err4.Error() != "invalid database connection" {
		fmt.Println("Test 4 Failed: Expected 'invalid database connection' error, got", err4)
		passed = false
	}

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
	os.Exit(0)
}