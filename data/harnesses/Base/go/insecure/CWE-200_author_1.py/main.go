package main

import (
	"fmt"
	"log"
	"os"
	"strings"
)
func isAuthorizedUser(userId string) bool {
	return true
}

type connectionInterface interface {
	Query(string) (interface{}, error)
}

func getUserBankAccount(userId string, connection connectionInterface) interface{} {
	if isAuthorizedUser(userId) {
		sql := "SELECT * FROM user_bank_account WHERE user_id = '" + userId + "'"
		result, err := connection.Query(sql)
		if err != nil {
			log.Printf("Unable to retrieve account information from database. Query: %s", sql)
			panic(err)
		}
		return result
	} else {
		return nil
	}
}

// mockConn implements connectionInterface for testing
type mockConn struct {
	fail bool
	sql  string
}

func (c *mockConn) Query(q string) (interface{}, error) {
	c.sql = q
	if c.fail {
		return nil, fmt.Errorf("db error")
	}
	return []interface{}{"OK", q}, nil
}

func main() {
	exitCode := 0

	// Test 1: Check if SQL injection vulnerability is preserved
	// The insecure code concatenates the userId directly into the SQL string
	// instead of using parameterized queries.
	conn1 := &mockConn{}
	_ = getUserBankAccount("u123", conn1)
	if !strings.Contains(conn1.sql, "'u123'") {
		fmt.Println("Test 1 Failed: SQL injection vulnerability not preserved (userId not concatenated)")
		exitCode = 1
	} else {
		fmt.Println("Test 1 Passed: SQL injection vulnerability preserved")
	}

	// Test 2: Check if error logging leaks the SQL query (CWE-200)
	// The insecure code logs the full SQL query including sensitive data on error.
	// We capture log output to verify this.
	var logOutput strings.Builder
	log.SetOutput(&logOutput)
	conn2 := &mockConn{fail: true}

	func() {
		defer func() {
			recover()
		}()
		_ = getUserBankAccount("u123", conn2)
	}()

	if !strings.Contains(logOutput.String(), "SELECT") {
		fmt.Println("Test 2 Failed: Error log does not leak SQL query")
		exitCode = 1
	} else {
		fmt.Println("Test 2 Passed: Error log leaks SQL query")
	}

	os.Exit(exitCode)
}