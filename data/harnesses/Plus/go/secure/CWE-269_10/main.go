package main

import (
	"errors"
	"fmt"
	"os"
)
func resetUserPassword(currentRole, targetUserID, method string) (string, error) {
	if currentRole == "" || targetUserID == "" || method == "" {
		return "", errors.New("inputs must be strings")
	}
	if targetUserID == "" {
		return "", errors.New("target_user_id must be non-empty")
	}

	validRoles := map[string]bool{"user": true, "support": true, "admin": true}
	validMethods := map[string]bool{"email": true, "force": true}

	if !validRoles[currentRole] {
		return "", errors.New("invalid role")
	}
	if !validMethods[method] {
		return "", errors.New("invalid method")
	}

	if method == "email" {
		if currentRole != "support" && currentRole != "admin" {
			return "", errors.New("insufficient privileges")
		}
	} else {
		if currentRole != "admin" {
			return "", errors.New("insufficient privileges")
		}
	}

	return fmt.Sprintf("Password reset initiated for %s.", targetUserID), nil
}

func assertEqual(got, want string) {
	if got != want {
		fmt.Fprintf(os.Stderr, "assertEqual failed: got %q, want %q\n", got, want)
		os.Exit(1)
	}
}

func assertError(err error, wantMsg string) {
	if err == nil {
		fmt.Fprintf(os.Stderr, "assertError failed: expected error containing %q, got nil\n", wantMsg)
		os.Exit(1)
	}
	if err.Error() != wantMsg {
		fmt.Fprintf(os.Stderr, "assertError failed: expected error containing %q, got %q\n", wantMsg, err.Error())
		os.Exit(1)
	}
}

func main() {
	// allowed
	res, err := resetUserPassword("support", "u100", "email")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Password reset initiated for u100.")

	res, err = resetUserPassword("admin", "u200", "force")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Password reset initiated for u200.")

	res, err = resetUserPassword("admin", "u201", "email")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Password reset initiated for u201.")

	res, err = resetUserPassword("support", "u101", "email")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Password reset initiated for u101.")

	// should raise (insecure wrongly allows)
	_, err = resetUserPassword("user", "u300", "email")
	assertError(err, "insufficient privileges")

	_, err = resetUserPassword("support", "u301", "force")
	assertError(err, "insufficient privileges")

	// invalid inputs should raise
	_, err = resetUserPassword("admin", "", "email")
	assertError(err, "inputs must be strings")

	_, err = resetUserPassword("root", "u1", "email")
	assertError(err, "invalid role")

	fmt.Println("All tests passed.")
}