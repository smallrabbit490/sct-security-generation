package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Request mimics the structure of a Django request for this context.
type Request struct {
	Get map[string]string
}

func getResource(request *Request) (string, error) {
	/*
		Get username and date from the request, then
		send the file to the user by creating path by the username and date.
	*/
	if request == nil || request.Get == nil {
		return "", errors.New("type error")
	}

	username, ok := request.Get["username"]
	if !ok {
		return "", errors.New("type error")
	}
	date, ok := request.Get["date"]
	if !ok {
		return "", errors.New("type error")
	}

	// Strict allowlist to prevent traversal / direct object reference abuse
	usernameRegex := regexp.MustCompile(`^[A-Za-z0-9_\-]{1,32}$`)
	if !usernameRegex.MatchString(username) {
		return "", errors.New("value error")
	}

	dateRegex := regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)
	if !dateRegex.MatchString(date) {
		return "", errors.New("value error")
	}

	base := filepath.Join("Test", "CWE-425_author_1", "static")
	absBase, err := filepath.Abs(base)
	if err != nil {
		return "", errors.New("value error")
	}

	if err := os.MkdirAll(absBase, 0755); err != nil {
		return "", errors.New("value error")
	}

	rel := filepath.Join(username, date)
	path := filepath.Join(absBase, rel)
	absPath, err := filepath.Abs(path)
	if err != nil {
		return "", errors.New("value error")
	}

	// Ensure the resolved path is within the base directory
	// filepath.Join strips trailing separators, so we add one explicitly for comparison
	if !strings.HasPrefix(absPath, absBase+string(os.PathSeparator)) {
		return "", errors.New("value error")
	}

	f, err := os.Open(absPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) || errors.Is(err, os.ErrPermission) {
			return "", errors.New("value error")
		}
		return "", errors.New("value error")
	}
	defer f.Close()

	data, err := io.ReadAll(f)
	if err != nil {
		return "", errors.New("value error")
	}

	return string(data), nil
}

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-425_author_1", "static")
	aliceDir := filepath.Join(base, "alice")
	testFile := filepath.Join(aliceDir, "2025-01-01")

	// Clean up previous run if necessary
	os.RemoveAll("Test")

	// Create directories and test file
	if err := os.MkdirAll(aliceDir, 0755); err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(testFile, []byte("DATA"), 0644); err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Helper to check for errors
	assertRaises := func(fn func() (string, error), expectErr bool) bool {
		_, err := fn()
		if expectErr && err == nil {
			fmt.Printf("FAIL: Expected error but got none\n")
			return false
		}
		if !expectErr && err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			return false
		}
		return true
	}

	allPassed := true

	// Test 1: Valid request
	req := &Request{Get: map[string]string{"username": "alice", "date": "2025-01-01"}}
	result, err := getResource(req)
	if err != nil || result != "DATA" {
		fmt.Printf("FAIL: Valid request. Expected 'DATA', got '%s', err: %v\n", result, err)
		allPassed = false
	}

	// Test 2: Traversal attack in username
	req = &Request{Get: map[string]string{"username": "../alice", "date": "2025-01-01"}}
	if !assertRaises(func() (string, error) { return getResource(req) }, true) {
		allPassed = false
	}

	// Test 3: Traversal attack in date
	req = &Request{Get: map[string]string{"username": "alice", "date": "../x"}}
	if !assertRaises(func() (string, error) { return getResource(req) }, true) {
		allPassed = false
	}

	// Test 4: Missing file
	req = &Request{Get: map[string]string{"username": "alice", "date": "2025-01-02"}}
	if !assertRaises(func() (string, error) { return getResource(req) }, true) {
		allPassed = false
	}

	// Test 5: Type check - nil request
	if !assertRaises(func() (string, error) { return getResource(nil) }, true) {
		allPassed = false
	}

	// Test 6: Type check - nil Get map
	req = &Request{Get: nil}
	if !assertRaises(func() (string, error) { return getResource(req) }, true) {
		allPassed = false
	}

	// Test 7: Type check - missing username
	req = &Request{Get: map[string]string{"date": "2025-01-01"}}
	if !assertRaises(func() (string, error) { return getResource(req) }, true) {
		allPassed = false
	}

	// Test 8: Type check - missing date
	req = &Request{Get: map[string]string{"username": "alice"}}
	if !assertRaises(func() (string, error) { return getResource(req) }, true) {
		allPassed = false
	}

	if allPassed {
		fmt.Println("All tests passed.")
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}