package main

import (
	"errors"
	"fmt"
	"os"
)
func grantAccess(role interface{}) (string, error) {
	strRole, ok := role.(string)
	if !ok {
		return "", errors.New("role must be a string")
	}
	if strRole == "admin" {
		return "Full access granted", nil
	}
	if strRole == "guest" {
		return "Read-only access granted", nil
	}
	return "", errors.New("invalid role")
}

func main() {
	passed := true

	// Helper to check results and fail on mismatch
	checkResult := func(result string, err error, expected string) {
		if err != nil {
			fmt.Printf("FAIL: unexpected error: %v\n", err)
			passed = false
			return
		}
		if result != expected {
			fmt.Printf("FAIL: expected %q, got %q\n", expected, result)
			passed = false
		}
	}

	// Helper to check that an error is returned
	checkError := func(err error, expectedMsg string) {
		if err == nil {
			fmt.Printf("FAIL: expected error with message %q, but got nil\n", expectedMsg)
			passed = false
			return
		}
		if err.Error() != expectedMsg {
			fmt.Printf("FAIL: expected error message %q, got %q\n", expectedMsg, err.Error())
			passed = false
		}
	}

	// valid roles
	result, err := grantAccess("admin")
	checkResult(result, err, "Full access granted")

	result, err = grantAccess("guest")
	checkResult(result, err, "Read-only access granted")

	// invalid role: insecure returns read-only, secure must raise
	_, err = grantAccess("invalid_role")
	checkError(err, "invalid role")

	// case mismatch should raise
	_, err = grantAccess("Admin")
	checkError(err, "invalid role")

	// empty role should raise
	_, err = grantAccess("")
	checkError(err, "invalid role")

	// whitespace role should raise
	_, err = grantAccess("   ")
	checkError(err, "invalid role")

	// non-string role should raise
	_, err = grantAccess(nil)
	checkError(err, "role must be a string")

	_, err = grantAccess(123)
	checkError(err, "role must be a string")

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}