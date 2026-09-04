package main

import (
	"fmt"
	"os"
)
func accessProjectFile(userRole, action, fileName string) (string, error) {
	permissions := map[string]map[string]bool{
		"viewer": {
			"view": true,
		},
		"contributor": {
			"view": true,
			"edit": true,
		},
		"project_admin": {
			"view":   true,
			"edit":   true,
			"delete": true,
		},
	}

	validActions := map[string]bool{
		"view":   true,
		"edit":   true,
		"delete": true,
	}

	rolePerms, roleOk := permissions[userRole]
	if !roleOk {
		return "", fmt.Errorf("unknown role")
	}

	if !validActions[action] {
		return "", fmt.Errorf("unknown action")
	}

	if rolePerms[action] {
		return fmt.Sprintf("Action permitted: %s", action), nil
	}

	return fmt.Sprintf("Action blocked: %s", action), nil
}

func main() {
	allPassed := true

	// Helper to assert equality of strings
	assertEqual := func(got, expected string) {
		if got != expected {
			fmt.Fprintf(os.Stderr, "Expected %q, got %q\n", expected, got)
			allPassed = false
		}
	}

	// Helper to assert that a function returns an error
	assertError := func(err error) {
		if err == nil {
			fmt.Fprintln(os.Stderr, "Expected an error but none was raised")
			allPassed = false
		}
	}

	// permitted
	res, err := accessProjectFile("viewer", "view", "project_charter.pdf")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		allPassed = false
	} else {
		assertEqual(res, "Action permitted: view")
	}

	res, err = accessProjectFile("contributor", "edit", "risk_analysis.docx")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		allPassed = false
	} else {
		assertEqual(res, "Action permitted: edit")
	}

	res, err = accessProjectFile("project_admin", "delete", "obsolete_data.csv")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		allPassed = false
	} else {
		assertEqual(res, "Action permitted: delete")
	}

	res, err = accessProjectFile("project_admin", "view", "anything.txt")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		allPassed = false
	} else {
		assertEqual(res, "Action permitted: view")
	}

	// blocked (insecure will incorrectly execute)
	res, err = accessProjectFile("viewer", "edit", "project_plan.xlsx")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		allPassed = false
	} else {
		assertEqual(res, "Action blocked: edit")
	}

	res, err = accessProjectFile("contributor", "delete", "confidential_info.docx")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		allPassed = false
	} else {
		assertEqual(res, "Action blocked: delete")
	}

	// invalid inputs must raise
	_, err = accessProjectFile("guest", "view", "x.txt")
	assertError(err)

	_, err = accessProjectFile("viewer", "run", "x.txt")
	assertError(err)

	if !allPassed {
		os.Exit(1)
	}
}