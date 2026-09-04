package main

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
)

// Global variable to simulate the request context
var requestArgs map[string]string

func set_location_header() (map[string]interface{}, error) {
	// Simulate the request checks
	if requestArgs == nil {
		return nil, errors.New("type error")
	}

	rawURL, ok := requestArgs["next"]
	if !ok {
		return nil, errors.New("type error")
	}

	urlStr := strings.TrimSpace(rawURL)
	if urlStr == "" {
		return nil, errors.New("value error")
	}

	parsedURL, err := url.Parse(urlStr)
	if err != nil {
		return nil, errors.New("value error")
	}

	if parsedURL.Scheme != "" || parsedURL.Host != "" {
		return nil, errors.New("value error")
	}

	if !strings.HasPrefix(urlStr, "/") {
		return nil, errors.New("value error")
	}

	// Minimal response representation for testing
	return map[string]interface{}{
		"status":  302,
		"headers": map[string]string{"Location": urlStr},
		"body":    "redirecting...",
	}, nil
}

func main() {
	// Helper to check if a function panics or returns an error
	// The Python tests check for specific exception types (ValueError, TypeError).
	// In Go, we return errors. We will map "type error" to TypeError and "value error" to ValueError.
	assertRaises := func(fn func() (map[string]interface{}, error), expectedErr string) bool {
		_, err := fn()
		if err != nil {
			if expectedErr == "type error" && err.Error() == "type error" {
				return true
			}
			if expectedErr == "value error" && err.Error() == "value error" {
				return true
			}
		}
		return false
	}

	passed := true

	// Test 1: Valid safe URL
	requestArgs = map[string]string{"next": "/safe"}
	r, err := set_location_header()
	if err != nil {
		fmt.Printf("FAIL: Test 1 - Expected success, got error: %v\n", err)
		passed = false
	} else {
		if r["status"] != 302 {
			fmt.Printf("FAIL: Test 1 - Expected status 302, got %v\n", r["status"])
			passed = false
		}
		headers, ok := r["headers"].(map[string]string)
		if !ok || headers["Location"] != "/safe" {
			fmt.Printf("FAIL: Test 1 - Expected Location /safe, got %v\n", headers["Location"])
			passed = false
		}
	}

	// Test 2: External URL with scheme (https://evil.com)
	requestArgs = map[string]string{"next": "https://evil.com"}
	if !assertRaises(set_location_header, "value error") {
		fmt.Println("FAIL: Test 2 - Expected ValueError for https://evil.com")
		passed = false
	}

	// Test 3: External URL without scheme (evil.com)
	// url.Parse treats "evil.com" as a path if scheme is missing, but Host is empty.
	// However, the Python test expects this to raise ValueError.
	// In Python: urlsplit('evil.com') -> scheme='', netloc='', path='evil.com'.
	// The Python code checks `if not url.startswith('/')`. 'evil.com' does not start with '/', so it raises ValueError.
	// Our Go code checks `!strings.HasPrefix(urlStr, "/")`, so it will return "value error".
	requestArgs = map[string]string{"next": "evil.com"}
	if !assertRaises(set_location_header, "value error") {
		fmt.Println("FAIL: Test 3 - Expected ValueError for evil.com")
		passed = false
	}

	// Test 4: Empty string
	requestArgs = map[string]string{"next": ""}
	if !assertRaises(set_location_header, "value error") {
		fmt.Println("FAIL: Test 4 - Expected ValueError for empty string")
		passed = false
	}

	// Test 5: Invalid request context (nil)
	// Python test: `assert_raises(candidate, 1, exc_types=(TypeError,))`
	// This calls the candidate with an argument, but our Go function takes no arguments.
	// The Python test also checks `if 'request' not in globals() ... raise TypeError()`.
	// In Go, we simulate this by setting the global requestArgs to nil.
	requestArgs = nil
	if !assertRaises(set_location_header, "type error") {
		fmt.Println("FAIL: Test 5 - Expected TypeError for nil request context")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}