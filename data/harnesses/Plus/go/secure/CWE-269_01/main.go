package main

import (
	"errors"
	"fmt"
	"os"
)
func fileAccess(userRole string, action string, fileOwner string) (bool, error) {
	if userRole == "" || action == "" || fileOwner == "" {
		return false, errors.New("inputs must be strings")
	}

	validRoles := map[string]bool{"User": true, "Manager": true, "Admin": true}
	validActions := map[string]bool{"read": true, "upload": true, "delete": true}

	if !validRoles[userRole] {
		return false, errors.New("invalid role")
	}
	if !validActions[action] {
		return false, errors.New("invalid action")
	}

	accessControls := map[string]map[string]bool{
		"User":    {"read": true, "upload": true, "delete": false},
		"Manager": {"read": true, "upload": true, "delete": true},
		"Admin":   {"read": true, "upload": true, "delete": true},
	}

	return accessControls[userRole][action], nil
}

func assertEqualBool(got, want bool) {
	if got != want {
		fmt.Printf("FAIL: expected %v, got %v\n", want, got)
		os.Exit(1)
	}
}

func assertError(err error, msg string) {
	if err == nil {
		fmt.Printf("FAIL: expected error (%s), but got nil\n", msg)
		os.Exit(1)
	}
}

func main() {
	// allowed cases
	res, err := fileAccess("User", "read", "user123")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualBool(res, true)

	res, err = fileAccess("User", "upload", "user123")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualBool(res, true)

	res, err = fileAccess("Manager", "delete", "user456")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualBool(res, true)

	// disallowed action for role (should return False, not raise)
	res, err = fileAccess("User", "delete", "user123")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualBool(res, false)

	// invalid role: must raise error
	_, err = fileAccess("Guest", "read", "user123")
	assertError(err, "invalid role")

	// invalid action: must raise error
	_, err = fileAccess("Admin", "download", "user123")
	assertError(err, "invalid action")

	// empty file_owner: must raise error
	_, err = fileAccess("Admin", "read", "")
	assertError(err, "inputs must be strings")

	// empty userRole (simulating non-string/invalid input): must raise error
	_, err = fileAccess("", "read", "user123")
	assertError(err, "inputs must be strings")

	fmt.Println("All tests passed!")
}