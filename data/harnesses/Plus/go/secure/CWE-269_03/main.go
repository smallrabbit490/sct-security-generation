package main

import (
	"errors"
	"fmt"
	"os"
)
func edit_article(role interface{}, articleContent interface{}) (string, error) {
	roleStr, ok := role.(string)
	if !ok {
		return "", errors.New("role and article_content must be strings")
	}

	contentStr, ok := articleContent.(string)
	if !ok {
		return "", errors.New("role and article_content must be strings")
	}

	if roleStr == "editor" {
		return contentStr + " [Edited]", nil
	}
	if roleStr == "reader" {
		return contentStr, nil
	}

	return "", errors.New("invalid role")
}

func assertEqual(got string, expected string) {
	if got != expected {
		fmt.Printf("FAIL: expected %q, got %q\n", expected, got)
		os.Exit(1)
	}
}

func assertError(err error, expectedMsg string) {
	if err == nil {
		fmt.Printf("FAIL: expected error containing %q, got nil\n", expectedMsg)
		os.Exit(1)
	}
	if err.Error() != expectedMsg {
		fmt.Printf("FAIL: expected error containing %q, got %q\n", expectedMsg, err.Error())
		os.Exit(1)
	}
}

func main() {
	// editor edits
	res, err := edit_article("editor", "Sample article")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Sample article [Edited]")

	res, err = edit_article("editor", "")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, " [Edited]")

	// reader unchanged
	res, err = edit_article("reader", "Sample article")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Sample article")

	res, err = edit_article("reader", "")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "")

	// invalid role: secure must raise
	res, err = edit_article("invalid_role", "Sample article")
	assertError(err, "invalid role")

	// invalid type for role
	res, err = edit_article(nil, "Sample article")
	assertError(err, "role and article_content must be strings")

	// invalid type for content
	res, err = edit_article("reader", nil)
	assertError(err, "role and article_content must be strings")

	// Ensure res is used to avoid unused variable compilation errors
	_ = res

	fmt.Println("All tests passed.")
}