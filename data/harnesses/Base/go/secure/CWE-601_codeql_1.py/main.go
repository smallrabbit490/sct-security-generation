package main

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
)

// Global variable to simulate the Flask request object.
// In a real application, this would be passed as a parameter.
var requestArgs map[string][]string

func redirect() (string, error) {
	// Check if request is available and has args
	if requestArgs == nil {
		return "", errors.New("invalid request")
	}

	// Get the 'target' parameter
	targetValues, ok := requestArgs["target"]
	if !ok || len(targetValues) == 0 {
		return "", errors.New("target is required")
	}
	target := targetValues[0]

	// Strip whitespace
	target = strings.TrimSpace(target)
	if target == "" {
		return "", errors.New("target cannot be empty")
	}

	// CWE-601: only allow relative paths
	parts, err := url.Parse(target)
	if err != nil {
		return "", errors.New("invalid URL")
	}
	if parts.Scheme != "" || parts.Host != "" {
		return "", errors.New("absolute URLs are not allowed")
	}
	if !strings.HasPrefix(target, "/") {
		return "", errors.New("URL must start with /")
	}
	if strings.Contains(target, "\\") {
		return "", errors.New("backslashes are not allowed")
	}

	return target, nil
}

func main() {
	// Helper to assert that a function raises an error
	assertRaises := func(fn func() (string, error)) {
		_, err := fn()
		if err == nil {
			fmt.Println("FAIL: Expected error but got none")
			os.Exit(1)
		}
	}

	// Test 1: Valid relative path
	requestArgs = map[string][]string{"target": {"/home"}}
	result, err := redirect()
	if err != nil || result != "/home" {
		fmt.Printf("FAIL: Test 1 failed. Expected '/home', got '%s', err: %v\n", result, err)
		os.Exit(1)
	}

	// Test 2: Valid relative path with query
	requestArgs = map[string][]string{"target": {"/a/b?x=1"}}
	result, err = redirect()
	if err != nil || result != "/a/b?x=1" {
		fmt.Printf("FAIL: Test 2 failed. Expected '/a/b?x=1', got '%s', err: %v\n", result, err)
		os.Exit(1)
	}

	// Test 3: External redirects rejected (https)
	requestArgs = map[string][]string{"target": {"https://evil.com"}}
	assertRaises(redirect)

	// Test 4: External redirects rejected (protocol-relative)
	requestArgs = map[string][]string{"target": {"//evil.com/path"}}
	assertRaises(redirect)

	// Test 5: Missing / empty rejected
	requestArgs = map[string][]string{"target": {""}}
	assertRaises(redirect)

	// Test 6: Extra arg rejected (simulated by checking nil requestArgs)
	// In the Python test, it calls candidate(1). Since our Go redirect takes no args,
	// we simulate the "TypeError" condition by ensuring the request context is invalid or nil.
	// The Python test specifically checks TypeError for wrong arguments.
	// Here we verify that if requestArgs is nil, we get an error.
	requestArgs = nil
	assertRaises(redirect)

	fmt.Println("All tests passed.")
}