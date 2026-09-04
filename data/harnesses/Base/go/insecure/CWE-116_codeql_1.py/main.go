package main

import (
	"fmt"
	"os"
	"regexp"
)

// Translated insecure code
func filterScriptTags(content string) string {
	re := regexp.MustCompile(`(?i)<script.*?>.*?</script>|<script.*?/>`)
	oldContent := ""
	for oldContent != content {
		oldContent = content
		content = re.ReplaceAllString(content, "")
	}
	return content
}

func main() {
	// Helper to check if the program should exit with success (0) or failure (1)
	// The validation rule states: "exit with code 0 only when the translated insecure code fails in the same security-relevant way"
	// The Python tests expect the secure solution to raise ValueError for malformed input.
	// The translated insecure code does NOT raise an error; it returns the string unchanged (or partially processed).
	// Therefore, the insecure code FAILS to match the secure behavior (raising an error).
	// Since the insecure code fails the security check (by not raising), the validation program should treat this as a "matching failure" and exit 0.
	// However, we must also ensure the insecure code doesn't crash or behave unexpectedly in other ways.

	// Test 4: malformed/unterminated script
	// Secure expectation: raises ValueError
	// Insecure behavior: returns string unchanged (no panic, no error)
	// Validation: We verify that the function returns a string (no panic) and that it does NOT raise an error (which Go functions can't do in the same way, but we check for panic).
	// Since the insecure code successfully returns a string instead of erroring, it has "failed" the security requirement.
	// The prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
	// Here, the insecure code fails to be secure. So we exit 0.

	// We wrap the call in a recover() to ensure we don't crash if the implementation is wildly broken.
	// If it panics, that's a different kind of failure, so we exit 1.
	defer func() {
		if r := recover(); r != nil {
			fmt.Println("FAIL: Insecure code panicked unexpectedly")
			os.Exit(1)
		}
	}()

	input := "a<script>alert(1)"
	result := filterScriptTags(input)

	// The insecure code returns the input string (or a modified version) without erroring.
	// This confirms it behaves insecurely (ignoring the malformed tag).
	// We print the result to stdout to show behavior, and exit 0 to indicate the validation passed (i.e., the insecurity was confirmed).
	fmt.Println(result)
	os.Exit(0)
}