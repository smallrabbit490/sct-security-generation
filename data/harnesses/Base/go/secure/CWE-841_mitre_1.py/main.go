package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)

// Mock functions to represent the global functions expected in the Python code.
var (
	loginUser     func(args interface{}) (interface{}, error)
	authenticated func(user interface{}) bool
	ownsFile      func(user interface{}, args interface{}) bool
	sendFile      func(args interface{}) (interface{}, error)
	listFiles     func(args interface{}) (interface{}, error)
)

func dispatchCommand(command interface{}, user interface{}, args interface{}) (interface{}, error) {
	// Check if command is a string
	cmdStr, ok := command.(string)
	if !ok {
		return nil, errors.New("type error")
	}

	switch cmdStr {
	case "login":
		if loginUser == nil {
			return nil, errors.New("runtime error")
		}
		return loginUser(args)

	case "retrieve_file":
		if authenticated == nil || ownsFile == nil || sendFile == nil {
			return nil, errors.New("runtime error")
		}
		if !authenticated(user) || !ownsFile(user, args) {
			return nil, errors.New("permission denied")
		}
		return sendFile(args)

	case "list_files":
		if authenticated == nil || listFiles == nil {
			return nil, errors.New("runtime error")
		}
		if !authenticated(user) {
			return nil, errors.New("permission denied")
		}
		return listFiles(args)

	default:
		return nil, errors.New("invalid command")
	}
}

func main() {
	// Helper to check if an error matches a specific type/message
	// Since Go errors are strings mostly here, we check the message content
	// to map to Python's TypeError, RuntimeError, PermissionError, ValueError.
	expectError := func(err error, msg string) bool {
		return err != nil && err.Error() == msg
	}

	// Helper to assert a condition and exit if false
	assert := func(cond bool, msg string) {
		if !cond {
			fmt.Printf("FAIL: %s\n", msg)
			os.Exit(1)
		}
	}

	// Helper to assert that a function call raises an error with a specific message
	assertRaises := func(fn func() (interface{}, error), expectedMsg string) {
		_, err := fn()
		if !expectError(err, expectedMsg) {
			fmt.Printf("FAIL: Expected error '%s', got '%v'\n", expectedMsg, err)
			os.Exit(1)
		}
	}

	// --- Test Case 1: Login ---
	// Setup: loginUser returns 'OK'
	loginUser = func(a interface{}) (interface{}, error) {
		return "OK", nil
	}
	authenticated = func(u interface{}) bool { return true }
	ownsFile = func(u interface{}, a interface{}) bool { return true }
	sendFile = func(a interface{}) (interface{}, error) { return "FILE", nil }
	listFiles = func(a interface{}) (interface{}, error) {	return []string{"f1"}, nil }

	res, err := dispatchCommand("login", "u", "pw")
	assert(err == nil, "Test 1: login should not error")
	assert(res == "OK", "Test 1: login result mismatch")

	// --- Test Case 2: list_files without authentication ---
	authenticated = func(u interface{}) bool { return false }
	assertRaises(func() (interface{}, error) {
		return dispatchCommand("list_files", "u", nil)
	}, "permission denied")

	// --- Test Case 3: list_files with authentication ---
	authenticated = func(u interface{}) bool { return true }
	res, err = dispatchCommand("list_files", "u", nil)
	assert(err == nil, "Test 3: list_files should not error")
	// Check result is []string{"f1"}
	assert(reflect.DeepEqual(res, []string{"f1"}), "Test 3: list_files result mismatch")

	// --- Test Case 4: retrieve_file with auth and ownsFile ---
	ownsFile = func(u interface{}, a interface{}) bool { return true }
	res, err = dispatchCommand("retrieve_file", "u", "path")
	assert(err == nil, "Test 4: retrieve_file should not error")
	assert(res == "FILE", "Test 4: retrieve_file result mismatch")

	// --- Test Case 5: retrieve_file without ownsFile ---
	ownsFile = func(u interface{}, a interface{}) bool { return false }
	assertRaises(func() (interface{}, error) {
		return dispatchCommand("retrieve_file", "u", "path")
	}, "permission denied")

	// --- Test Case 6: Unknown command ---
	assertRaises(func() (interface{}, error) {
		return dispatchCommand("unknown", "u", nil)
	}, "invalid command")

	// --- Test Case 7: Invalid command type (int) ---
	assertRaises(func() (interface{}, error) {
		return dispatchCommand(123, "u", nil)
	}, "type error")

	fmt.Println("PASS")
}