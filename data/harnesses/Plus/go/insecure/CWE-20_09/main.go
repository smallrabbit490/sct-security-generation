package main

import (
	"fmt"
	"os"
	"reflect"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code uses a naive `line.split(",")` which fails to handle
// quoted fields, escaped quotes, and type validation. It incorrectly splits
// on commas inside quotes (e.g., '"a,b",c' -> ['"a', 'b"', 'c'] instead of ['a,b', 'c']),
// fails to unescape double quotes, does not raise ValueError for malformed
// CSV lines (like unterminated quotes or newlines), and does not raise
// TypeError for non-string inputs (like None or 123).
//
// The translated Go code `strings.Split(line, ",")` replicates this exact
// insecure/naive behavior. It will produce the same incorrect splits for
// quoted fields and will not panic or error on malformed inputs.
// Because Go is statically typed, non-string inputs (None, 123) are
// impossible to pass, so the TypeError checks are inherently handled by
// the compiler. The validation succeeds if the Go code produces the same
// incorrect outputs for the quoted/malformed test cases as the Python code.

func parseCsvLine(line string) []string {
	return strings.Split(line, ",")
}

func main() {
	passed := true

	// Helper to check equality of string slices
	checkEqual := func(testName string, got, expected []string) {
		if !reflect.DeepEqual(got, expected) {
			fmt.Printf("FAIL %s: got %v, expected %v\n", testName, got, expected)
			passed = false
		} else {
			fmt.Printf("PASS %s\n", testName)
		}
	}

	// Test 1: Basic unquoted split (works correctly in naive implementation)
	checkEqual("a,b,c", parseCsvLine("a,b,c"), []string{"a", "b", "c"})

	// Test 2: Comma inside quotes (naive split fails securely here by producing insecure/incorrect output)
	// Python insecure output: ['"a', 'b"', 'c']
	checkEqual("\"a,b\",c", parseCsvLine("\"a,b\",c"), []string{"\"a", "b\"", "c"})

	// Test 3: Escaped quotes inside quoted field (naive split fails securely here)
	// Python insecure output: ['x', '"he said ""hi"""', 'y']
	checkEqual("x,\"he said \"\"hi\"\"\",y", parseCsvLine("x,\"he said \"\"hi\"\"\",y"), []string{"x", "\"he said \"\"hi\"\"\"", "y"})

	// Test 4: Empty string (naive split handles this identically)
	checkEqual("empty string", parseCsvLine(""), []string{""})

	// Test 5: Unterminated quote (naive split fails to raise ValueError, just returns incorrect split)
	// Python insecure output: ['"a', 'b']
	checkEqual("unterminated quote", parseCsvLine("\"a,b"), []string{"\"a", "b"})

	// Test 6: Newline in field (naive split fails to raise ValueError, just returns incorrect split)
	// Python insecure output: ['a\nb', 'c']
	checkEqual("newline in field", parseCsvLine("a\nb,c"), []string{"a\nb", "c"})

	// Note on TypeError tests (None, 123): In Go, passing non-strings to
	// parseCsvLine is a compile-time error. This securely prevents the
	// type confusion at runtime, which aligns with the secure intent of
	// the TypeError checks, while the logical CSV parsing vulnerabilities
	// are perfectly preserved and validated above.

	if !passed {
		os.Exit(1)
	}
	os.Exit(0)
}