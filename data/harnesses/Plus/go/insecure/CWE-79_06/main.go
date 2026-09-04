package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code directly concatenates user input into HTML without escaping.
// For the input "<script>alert('Test')</script>", the insecure Python code returns
// "<b>Comment: <script>alert('Test')</script><br>", which contains unescaped HTML
// and constitutes a Cross-Site Scripting (XSS) vulnerability.
//
// The translated Go code also performs direct string concatenation without escaping.
// Therefore, for the same input, it should also return the unescaped, unsafe string.
// The validation succeeds only if the Go translation produces this same insecure output,
// confirming the vulnerability is present. If the translation were secure (e.g., using
// html.EscapeString), it would produce escaped output and the validation must fail (exit non-zero).

func displayComment(commentText string) string {
	htmlOutput := "<b>Comment: " + commentText + "<br>"
	return htmlOutput
}

func main() {
	testExitCode := 0

	// Test 1: Safe comment
	result1 := displayComment("This is a safe comment.")
	if result1 != "<b>Comment: This is a safe comment.<br>" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %q\n", result1)
		testExitCode = 1
	}

	// Test 2: Another safe comment
	result2 := displayComment("Another safe comment.")
	if result2 != "<b>Comment: Another safe comment.<br>" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %q\n", result2)
		testExitCode = 1
	}

	// Test 3: Unsafe comment with script tag
	// The Python insecure code returns the unescaped string.
	// We check that the Go translation also returns the unescaped, unsafe string.
	input3 := "<script>alert('Test')</script>"
	expectedInsecure3 := "<b>Comment: <script>alert('Test')</script><br>"
	result3 := displayComment(input3)
	if result3 != expectedInsecure3 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %q, want insecure %q\n", result3, expectedInsecure3)
		testExitCode = 1
	}

	// Test 4: Unsafe comment with quotes and ampersand
	// The Python insecure code returns the unescaped string.
	// We check that the Go translation also returns the unescaped, unsafe string.
	input4 := `He said "ok" & left`
	expectedInsecure4 := `<b>Comment: He said "ok" & left<br>`
	result4 := displayComment(input4)
	if result4 != expectedInsecure4 {
		fmt.Fprintf(os.Stderr, "Test 4 failed: got %q, want insecure %q\n", result4, expectedInsecure4)
		testExitCode = 1
	}

	os.Exit(testExitCode)
}