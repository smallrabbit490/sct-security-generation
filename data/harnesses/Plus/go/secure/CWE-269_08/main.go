package main

import (
	"errors"
	"fmt"
	"os"
)
func updateUserRole(userID int, newRole string, currentUserRole string) (string, error) {
	validRoles := map[string]bool{"guest": true, "member": true, "admin": true}

	if !validRoles[currentUserRole] {
		return "", errors.New("invalid current_user_role")
	}

	if currentUserRole != "admin" {
		return "", errors.New("insufficient privileges")
	}

	if !validRoles[newRole] {
		return "", errors.New("invalid new_role")
	}

	return fmt.Sprintf("User %d role updated to %s.", userID, newRole), nil
}

func main() {
	passed := true

	assertEqual := func(expected, got string, err error) {
		if err != nil {
			fmt.Printf("FAIL: expected '%s', got error '%v'\n", expected, err)
			passed = false
			return
		}
		if expected != got {
			fmt.Printf("FAIL: expected '%s', got '%s'\n", expected, got)
			passed = false
		}
	}

	assertError := func(err error, expectedMsg string) {
		if err == nil {
			fmt.Printf("FAIL: expected error containing '%s', but got nil\n", expectedMsg)
			passed = false
			return
		}
		if err.Error() != expectedMsg {
			fmt.Printf("FAIL: expected error containing '%s', got '%s'\n", expectedMsg, err.Error())
			passed = false
		}
	}

	// admin allowed
	result, err := updateUserRole(1001, "member", "admin")
	assertEqual("User 1001 role updated to member.", result, err)

	result, err = updateUserRole(1003, "admin", "admin")
	assertEqual("User 1003 role updated to admin.", result, err)

	// non-admin: must raise insufficient privileges
	_, err = updateUserRole(1002, "admin", "member")
	assertError(err, "insufficient privileges")

	// invalid new_role: must raise invalid new_role
	_, err = updateUserRole(1004, "superadmin", "admin")
	assertError(err, "invalid new_role")

	// invalid current_user_role: must raise invalid current_user_role
	_, err = updateUserRole(1005, "guest", "root")
	assertError(err, "invalid current_user_role")

	// invalid new_role type (empty string acts as invalid/None equivalent): must raise invalid new_role
	_, err = updateUserRole(1006, "", "admin")
	assertError(err, "invalid new_role")

	// current_user_role wrong type (empty string acts as invalid/None equivalent): must raise invalid current_user_role
	_, err = updateUserRole(1007, "member", "")
	assertError(err, "invalid current_user_role")

	// new_role 'guest' by admin
	result, err = updateUserRole(1008, "guest", "admin")
	assertEqual("User 1008 role updated to guest.", result, err)

	if !passed {
		os.Exit(1)
	}
}