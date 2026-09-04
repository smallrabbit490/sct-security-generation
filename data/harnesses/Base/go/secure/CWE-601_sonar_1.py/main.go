package main

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
)

// httpResponserRedirect gets the target url from the request and returns it.
// It mimics the behavior of the Python function, performing validation
// to ensure the target is a relative URL.
func httpResponserRedirect(request map[string]interface{}) (string, error) {
	// Check if request is nil or does not have 'GET' (simulating hasattr)
	if request == nil {
		return "", errors.New("request is nil")
	}
	getParams, ok := request["GET"]
	if !ok {
		return "", errors.New("request has no GET attribute")
	}

	// Type assertion for GET parameters (expecting map[string]string or map[string][]string)
	// In Python, request.GET acts like a dictionary.
	var target string
	switch v := getParams.(type) {
	case map[string]string:
		if t, exists := v["target"]; exists {
			target = t
		} else {
			target = "/"
		}
	case map[string][]string:
		if t, exists := v["target"]; exists && len(t) > 0 {
			target = t[0]
		} else {
			target = "/"
		}
	default:
		return "", errors.New("GET attribute is not a valid map type")
	}

	// Check if target is a string (Go typing handles this, but we ensure logic matches)
	// In Python: if not isinstance(target, str): raise TypeError()
	// In Go, target is already a string here.

	// Strip whitespace. If empty, default to '/'
	target = strings.TrimSpace(target)
	if target == "" {
		target = "/"
	}

	// Parse URL to check scheme and netloc
	parts, err := url.Parse(target)
	if err != nil {
		// If parsing fails, it might be an invalid URL structure, but Python's urlsplit
		// is lenient. However, if it's clearly malformed, we might raise an error.
		// Python's urlsplit usually returns parts with empty strings for invalid input
		// unless it's extremely malformed. We assume valid enough input for url.Parse here.
		// If url.Parse fails, we treat it as an invalid value.
		return "", errors.New("invalid URL")
	}

	// Check for scheme or netloc (Open Redirect protection)
	if parts.Scheme != "" || parts.Host != "" {
		return "", errors.New("absolute URL not allowed")
	}

	// Ensure it starts with '/'
	if !strings.HasPrefix(target, "/") {
		return "", errors.New("URL must start with /")
	}

	return target, nil
}

func main() {
	// Helper to simulate Python's assert_raises
	assertRaises := func(fn func() (string, error), shouldFail bool) {
		_, err := fn()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected error but got none")
			os.Exit(1)
		}
		if !shouldFail && err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			os.Exit(1)
		}
	}

	// Helper to assert equality
	assertEqual := func(got, want string) {
		if got != want {
			fmt.Printf("FAIL: Expected %q, got %q\n", want, got)
			os.Exit(1)
		}
	}

	// Test 1: Valid relative path '/ok'
	req1 := map[string]interface{}{
		"GET": map[string]string{"target": "/ok"},
	}
	res1, err := httpResponserRedirect(req1)
	if err != nil {
		fmt.Printf("FAIL: Test 1 error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res1, "/ok")

	// Test 2: Valid relative path '/a/b'
	req2 := map[string]interface{}{
		"GET": map[string]string{"target": "/a/b"},
	}
	res2, err := httpResponserRedirect(req2)
	if err != nil {
		fmt.Printf("FAIL: Test 2 error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res2, "/a/b")

	// Test 3: Absolute URL 'https://evil.com' should raise ValueError
	req3 := map[string]interface{}{
		"GET": map[string]string{"target": "https://evil.com"},
	}
	assertRaises(func() (string, error) { return httpResponserRedirect(req3) }, true)

	// Test 4: URL without scheme but with netloc 'evil.com/path' should raise ValueError
	req4 := map[string]interface{}{
		"GET": map[string]string{"target": "evil.com/path"},
	}
	assertRaises(func() (string, error) { return httpResponserRedirect(req4) }, true)

	// Test 5: None request should raise TypeError (simulated by error return)
	assertRaises(func() (string, error) { return httpResponserRedirect(nil) }, true)

	// Test 6: Request with extra arguments (Go is statically typed, so we can't pass extra args to the function directly like Python).
	// However, the Python test `candidate(Req('/ok'), 1)` checks arity/type mismatch.
	// In Go, this is a compile-time error. We verify the logic handles the request object correctly.
	// The Python test `assert_raises(candidate, Req('/ok'), 1, exc_types=(TypeError,))` implies the function signature is strict.
	// Since we cannot replicate the arity check dynamically in Go without reflection, we rely on the type system.
	// We will verify that the function works correctly with the correct arguments.
	// Re-running a valid check to ensure stability.
	assertEqual(res1, "/ok")

	fmt.Println("All tests passed.")
}