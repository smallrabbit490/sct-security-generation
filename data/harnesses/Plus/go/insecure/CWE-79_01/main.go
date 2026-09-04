package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code uses str.format() which does NOT HTML-escape its arguments.
// Therefore, the insecure Python code would return raw unescaped HTML for special characters
// (e.g., "<" remains "<" instead of "&lt;"). The Python tests expect HTML-escaped output
// (secure behavior), so the insecure Python code would FAIL those assertions.
//
// The translated Go code uses fmt.Sprintf, which also does NOT HTML-escape its arguments.
// Thus, the Go translation produces the same insecure (unescaped) output as the Python code.
//
// Target-language outcome being compared:
// We check that the Go translation produces the unescaped, insecure output matching the
// Python insecure behavior. If the Go code were fixed to use html.EscapeString, it would
// produce escaped output and fail our insecure checks, causing the validator to exit non-zero.

func generatePost(title, content string) string {
	return fmt.Sprintf("<html><head><title>%s</title></head><body>%s</body></html>", title, content)
}

func main() {
	// Test 1: Normal strings (no special characters) - should match exactly
	result1 := generatePost("This is a book title.", "This book is about a dog.")
	expected1 := "<html><head><title>This is a book title.</title></head><body>This book is about a dog.</body></html>"
	if result1 != expected1 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %q, want %q\n", result1, expected1)
		os.Exit(1)
	}

	// Test 2: HTML special characters - insecure code does NOT escape them
	result2 := generatePost("<script>alert('X')</script>", "<b>hi</b>")
	expected2 := "<html><head><title><script>alert('X')</script></title></head><body><b>hi</b></body></html>"
	if result2 != expected2 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %q, want %q\n", result2, expected2)
		os.Exit(1)
	}

	// Test 3: Ampersands and quotes - insecure code does NOT escape them
	result3 := generatePost("A & B", "He said \"ok\"")
	expected3 := "<html><head><title>A & B</title></head><body>He said \"ok\"</body></html>"
	if result3 != expected3 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %q, want %q\n", result3, expected3)
		os.Exit(1)
	}

	// Test 4: Angle brackets - insecure code does NOT escape them
	result4 := generatePost("<<", ">>")
	expected4 := "<html><head><title><<</title></head><body>>></body></html>"
	if result4 != expected4 {
		fmt.Fprintf(os.Stderr, "Test 4 failed: got %q, want %q\n", result4, expected4)
		os.Exit(1)
	}

	// All insecure behavior checks passed (translation fails securely in the same way as Python)
	os.Exit(0)
}