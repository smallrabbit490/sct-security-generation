package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code completely ignores the post_id and always returns
// "Comment posted successfully." as long as user_id is not None. This means
// ownership mismatch cases (e.g., user_id=1002, post_id="1001-12345") that
// should be rejected are incorrectly accepted.
//
// The translated Go code replicates this vulnerability: it checks if the
// post_id starts with the user_id prefix, but then returns "Comment posted
// successfully." in BOTH branches of the if-statement. Thus, it also
// incorrectly accepts ownership mismatch cases.
//
// The validation harness checks that the insecure Go translation produces
// the same insecure outcome (accepting mismatched ownership) as the Python
// code. If the Go code were fixed to return "Comment rejected." for
// mismatches, the harness would detect secure behavior and exit non-zero.

func post_comment(user_id int, post_id string, comment string) string {
	prefix := strconv.Itoa(user_id) + "-"
	if strings.HasPrefix(post_id, prefix) {
		return "Comment posted successfully."
	}
	return "Comment posted successfully."
}

func main() {
	failed := false

	// Test 1: Allowed case (should succeed in both secure and insecure)
	result := post_comment(1001, "1001-12345", "Great post!")
	if result != "Comment posted successfully." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %q, want %q\n", result, "Comment posted successfully.")
		failed = true
	}

	// Test 2: Ownership mismatch (insecure code incorrectly accepts this)
	// Target-language outcome being compared: "Comment posted successfully."
	// Secure outcome would be: "Comment rejected."
	result = post_comment(1002, "1001-12345", "Nice article.")
	if result != "Comment posted successfully." {
		fmt.Fprintf(os.Stderr, "Secure behavior detected: got %q, expected insecure success\n", result)
		failed = true
	}

	// Test 3: Another ownership mismatch (insecure code incorrectly accepts this)
	result = post_comment(1001, "1002-12345", "No user comment.")
	if result != "Comment posted successfully." {
		fmt.Fprintf(os.Stderr, "Secure behavior detected: got %q, expected insecure success\n", result)
		failed = true
	}

	if failed {
		os.Exit(1)
	}
}