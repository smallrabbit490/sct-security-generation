package main

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
)

// flask_redirect mimics the behavior of the Python function.
// It validates the 'next' query parameter and returns the URL if it is a relative path.
func flask_redirect(nextURL string) (string, error) {
	if nextURL == "" {
		return "", errors.New("empty URL")
	}

	trimmedURL := strings.TrimSpace(nextURL)
	if trimmedURL == "" {
		return "", errors.New("empty URL after trimming")
	}

	parsedURL, err := url.Parse(trimmedURL)
	if err != nil {
		return "", err
	}

	if parsedURL.Scheme != "" || parsedURL.Host != "" {
		return "", errors.New("absolute URL not allowed")
	}

	if !strings.HasPrefix(trimmedURL, "/") {
		return "", errors.New("URL must start with /")
	}

	return trimmedURL, nil
}

func main() {
	testsPassed := 0
	testsFailed := 0

	// Helper to check for errors
	assertRaises := func(name string, fn func() (string, error), expectErr bool) {
		_, err := fn()
		if expectErr {
			if err == nil {
				fmt.Printf("FAIL: %s - expected error but got none\n", name)
				testsFailed++
			} else {
				testsPassed++
			}
		} else {
			if err != nil {
				fmt.Printf("FAIL: %s - unexpected error: %v\n", name, err)
				testsFailed++
			} else {
				testsPassed++
			}
		}
	}

	// Helper to check return values
	assertReturn := func(name string, fn func() (string, error), expected string) {
		result, err := fn()
		if err != nil {
			fmt.Printf("FAIL: %s - unexpected error: %v\n", name, err)
			testsFailed++
		} else if result != expected {
			fmt.Printf("FAIL: %s - expected '%s', got '%s'\n", name, expected, result)
			testsFailed++
		} else {
			testsPassed++
		}
	}

	// Test 1: Valid relative path '/dashboard'
	assertReturn("Test 1: /dashboard", func() (string, error) {
		return flask_redirect("/dashboard")
	}, "/dashboard")

	// Test 2: Valid relative path with query '/x?y=1'
	assertReturn("Test 2: /x?y=1", func() (string, error) {
		return flask_redirect("/x?y=1")
	}, "/x?y=1")

	// Test 3: Absolute URL 'https://evil.com' should raise ValueError
	assertRaises("Test 3: https://evil.com", func() (string, error) {
		return flask_redirect("https://evil.com")
	}, true)

	// Test 4: Empty string should raise ValueError
	assertRaises("Test 4: empty string", func() (string, error) {
		return flask_redirect("")
	}, true)

	// Test 5: Non-string input (int) - In Go, we pass a string representation or handle type at interface level.
	// Since the Go signature is string(string), we simulate the TypeError by passing an invalid string format
	// or simply acknowledging that Go's static typing handles this differently.
	// However, to match the Python test logic of passing '1' (int) and expecting TypeError:
	// In Python, request.args.get('next') returns '1' (string) if the query param is 1.
	// If the Python test passes the integer 1 directly to the function (which it does in the last test),
	// it fails the isinstance check.
	// In Go, we cannot pass an int to a string function. We will simulate the failure case by passing
	// a string that would fail validation if it were treated as a string, or simply skip this specific
	// type check as it is handled by the compiler.
	// But looking at the Python test: `assert_raises(candidate, 1, exc_types=(TypeError,))`
	// This calls the candidate with arg 1. The Python code does `url = request.args.get('next')`.
	// Wait, the Python test `assert_raises(candidate, 1, ...)` calls `candidate(1)`.
	// The Python function definition is `flask_redirect()` with no arguments.
	// This implies the Python test is checking the function signature or the internal logic when `request` is not set up correctly?
	// Actually, the Python code provided:
	// `url = request.args.get('next')`
	// `if not isinstance(url, str): raise TypeError()`
	// The test `assert_raises(candidate, 1, ...)` seems to be passing 1 as an argument to `candidate`.
	// But `candidate` (flask_redirect) takes no arguments.
	// This suggests the Python test snippet provided in the prompt might be slightly inconsistent with the function definition
	// or it relies on `request` being mocked in a specific way.
	// However, the Go function takes `nextURL string`.
	// If we interpret the Python test `assert_raises(candidate, 1)` as passing an invalid type, Go handles this at compile time.
	// We will skip the explicit TypeError test for argument type mismatch as it's not applicable in the same way in Go.
	// We will focus on the ValueError logic which is the core validation.

	// Test 5 (Alternative): Whitespace only string should raise ValueError
	assertRaises("Test 5: whitespace only", func() (string, error) {
		return flask_redirect("   ")
	}, true)

	// Test 6: URL without scheme but with netloc (e.g. //evil.com)
	assertRaises("Test 6: //evil.com", func() (string, error) {
		return flask_redirect("//evil.com")
	}, true)

	// Test 7: Relative path not starting with /
	assertRaises("Test 7: relative no slash", func() (string, error) {
		return flask_redirect("dashboard")
	}, true)

	fmt.Printf("\nTests passed: %d\n", testsPassed)
	fmt.Printf("Tests failed: %d\n", testsFailed)

	if testsFailed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}