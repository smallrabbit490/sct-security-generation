package main

import (
	"fmt"
	"os"
)
func modifyProjectAccess(projectID, userID, action, currentUserRole string) (string, error) {
	if projectID == "" || userID == "" || action == "" || currentUserRole == "" {
		return "", fmt.Errorf("all inputs must be strings")
	}

	if action != "add" && action != "remove" {
		return "", fmt.Errorf("invalid action")
	}

	if currentUserRole != "guest" && currentUserRole != "member" && currentUserRole != "project_manager" && currentUserRole != "admin" {
		return "", fmt.Errorf("invalid role")
	}

	if currentUserRole != "project_manager" && currentUserRole != "admin" {
		return "", fmt.Errorf("insufficient privileges")
	}

	return fmt.Sprintf("Access rights '%s' for user %s in project %s.", action, userID, projectID), nil
}

func main() {
	failed := false

	assertEqual := func(expected, got string) {
		if expected != got {
			fmt.Fprintf(os.Stderr, "expected %q, got %q\n", expected, got)
			failed = true
		}
	}

	assertError := func(err error, expectedMsg string) {
		if err == nil {
			fmt.Fprintf(os.Stderr, "expected error containing %q, got nil\n", expectedMsg)
			failed = true
		} else if err.Error() != expectedMsg {
			fmt.Fprintf(os.Stderr, "expected error containing %q, got %q\n", expectedMsg, err.Error())
			failed = true
		}
	}

	// allowed roles
	res, err := modifyProjectAccess("proj2", "user2", "add", "admin")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Access rights 'add' for user user2 in project proj2.", res)
	}

	res, err = modifyProjectAccess("proj3", "user3", "remove", "project_manager")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Access rights 'remove' for user user3 in project proj3.", res)
	}

	// guest: insufficient privileges
	_, err = modifyProjectAccess("proj1", "user1", "add", "guest")
	assertError(err, "insufficient privileges")

	// member: insufficient privileges
	_, err = modifyProjectAccess("proj1", "user1", "remove", "member")
	assertError(err, "insufficient privileges")

	// invalid action
	_, err = modifyProjectAccess("proj1", "user1", "grant", "admin")
	assertError(err, "invalid action")

	// invalid current_user_role
	_, err = modifyProjectAccess("proj1", "user1", "add", "superuser")
	assertError(err, "invalid role")

	// invalid types (empty strings simulate non-string/None inputs in Go)
	_, err = modifyProjectAccess("", "user1", "add", "admin")
	assertError(err, "all inputs must be strings")

	// empty project_id is still a string; secure allows (no rule against empty), so do a valid call
	res, err = modifyProjectAccess(" ", "u", "add", "admin")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual("Access rights 'add' for user u in project  .", res)
	}

	if failed {
		os.Exit(1)
	}
}