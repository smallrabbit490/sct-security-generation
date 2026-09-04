package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code does not validate the 'role' parameter. For an invalid role
// (e.g., 'invalid_role'), it silently returns the original content unchanged instead of
// raising a ValueError. The secure behavior requires raising an exception for invalid roles.
// The translated Go code must match this insecure behavior by returning the content
// without error for invalid roles, rather than returning an error.

// editArticle appends " [Edited]" to the content if the role is "editor".
// Insecurely, it does not validate the role and silently returns the original content
// for any unrecognized role.
func editArticle(role string, articleContent string) string {
	if role == "editor" {
		articleContent += " [Edited]"
	}
	return articleContent
}

func main() {
	failed := false

	// Test 1: editor edits
	result := editArticle("editor", "Sample article")
	if result != "Sample article [Edited]" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Sample article [Edited]', got '%s'\n", result)
		failed = true
	}

	// Test 2: editor edits empty content
	result = editArticle("editor", "")
	if result != " [Edited]" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected ' [Edited]', got '%s'\n", result)
		failed = true
	}

	// Test 3: reader unchanged
	result = editArticle("reader", "Sample article")
	if result != "Sample article" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 'Sample article', got '%s'\n", result)
		failed = true
	}

	// Test 4: reader unchanged empty content
	result = editArticle("reader", "")
	if result != "" {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected '', got '%s'\n", result)
		failed = true
	}

	// Test 5: invalid role - insecure behavior returns original content without error
	// Secure behavior would return an error here. We check that the insecure translation
	// matches the Python insecure outcome by returning the content unchanged.
	result = editArticle("invalid_role", "Sample article")
	if result != "Sample article" {
		fmt.Fprintf(os.Stderr, "Test 5 failed: insecure behavior expected 'Sample article', got '%s'\n", result)
		failed = true
	}

	if failed {
		os.Exit(1)
	}

	fmt.Println("All tests passed: insecure behavior matched")
	os.Exit(0)
}