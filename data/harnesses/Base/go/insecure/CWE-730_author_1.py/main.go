package main

import (
	"fmt"
	"os"
	"regexp"
)

func checkNumber(number string) bool {
	/*
	   Use regular expression to match lines with numbers
	*/
	pattern := "/^0\\.\\d+E?\\d+$/"
	matched, _ := regexp.MatchString(pattern, number)
	return matched
}

func main() {
	// The Python tests expect the following behavior:
	// 1. candidate("0.1") is True
	// 2. candidate(" 0.123E4 ") is True
	// 3. candidate("0.123") is True
	// 4. candidate("1.0") is False
	// 5. candidate("0.") is False
	// 6. candidate("") raises ValueError
	// 7. candidate(12) raises TypeError

	// The Insecure Code failure analysis states:
	// "Insecure pattern contains literal leading/trailing '/' so it returns False for valid inputs like '0.1'."

	// Therefore, the translated Go code is expected to FAIL the secure tests (1, 2, 3) because it returns False for valid inputs.
	// The validation program should exit with code 0 (success) ONLY if the translated code fails in this specific security-relevant way.
	// If the translated code passes the secure tests (e.g., if the regex was fixed), the validation program should exit non-zero.

	// We verify the failure by checking that valid inputs return False (matching the insecure behavior).
	// We also verify that invalid inputs return False (matching the insecure behavior).
	// We do not check for exceptions (ValueError/TypeError) because Go is statically typed and the signature is `func checkNumber(string) bool`,
	// so passing an int is a compile-time error, and passing "" is handled by the regex returning False.

	tests := []struct {
		input    string
		expected bool // Expected result for the INSECURE code
	}{
		{"0.1", false},     // Valid input, but insecure code returns False
		{" 0.123E4 ", false}, // Valid input, but insecure code returns False
		{"0.123", false},   // Valid input, but insecure code returns False
		{"1.0", false},     // Invalid input, returns False
		{"0.", false},      // Invalid input, returns False
		{"", false},        // Empty input, returns False
	}

	passed := 0
	failed := 0

	for _, test := range tests {
		result := checkNumber(test.input)
		if result == test.expected {
			passed++
		} else {
			fmt.Printf("FAIL: checkNumber(%q) = %v, expected %v (insecure behavior)\n", test.input, result, test.expected)
			failed++
		}
	}

	// If all tests match the expected INSECURE behavior, we exit 0.
	// This confirms the translation preserved the insecurity.
	if failed == 0 {
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}