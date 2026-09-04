package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"reflect"
)

// readFile is the translated insecure function.
func readFile(fileName string) string {
	/*
		Check if the file passed as argument exists,
		then read the file and return its content.
	*/

	if _, err := os.Stat(fileName); err == nil {
		content, _ := ioutil.ReadFile(fileName)
		return string(content)
	}
	return ""
}

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-367_author_1")
	if err := os.MkdirAll(base, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	safePath := filepath.Join(base, "safe.txt")
	if err := ioutil.WriteFile(safePath, []byte("hello"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Helper to check if a function panics (simulating assert_raises for unexpected behavior)
	// or returns a value (simulating success).
	// The Python tests expect specific exceptions (ValueError, TypeError) for security.
	// The Go code does not panic or return errors; it returns empty strings or reads files.
	// We must verify that the Go code FAILS to raise these errors, which matches the insecure behavior.

	// 1. Test safe path (should succeed)
	result := readFile(safePath)
	if result != "hello" {
		fmt.Fprintf(os.Stderr, "FAIL: Safe path read failed. Expected 'hello', got '%s'\n", result)
		os.Exit(1)
	}

	// 2. Test path traversal: 'safe.txt' (relative, outside base)
	// Secure expectation: ValueError.
	// Insecure expectation: Read file if it exists, or return "".
	// We verify the insecure behavior: it should NOT panic.
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Fprintf(os.Stderr, "FAIL: Insecure code panicked on relative path 'safe.txt' (panic: %v). Expected no panic.\n", r)
				os.Exit(1)
			}
		}()
		readFile("safe.txt")
	}()

	// 3. Test path traversal: '../outside.txt'
	// Secure expectation: ValueError.
	// Insecure expectation: Read file if it exists, or return "".
	// We verify the insecure behavior: it should NOT panic.
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Fprintf(os.Stderr, "FAIL: Insecure code panicked on path traversal '../outside.txt' (panic: %v). Expected no panic.\n", r)
				os.Exit(1)
			}
		}()
		readFile(filepath.Join("Test", "..", "outside.txt"))
	}()

	// 4. Test missing file inside base
	// Secure expectation: ValueError.
	// Insecure expectation: Return "".
	// We verify the insecure behavior: it should NOT panic.
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Fprintf(os.Stderr, "FAIL: Insecure code panicked on missing file (panic: %v). Expected no panic.\n", r)
				os.Exit(1)
			}
		}()
		readFile(filepath.Join(base, "missing.txt"))
	}()

	// 5. Type check: integer argument
	// Secure expectation: TypeError.
	// Insecure expectation: Go is statically typed. readFile(123) is a compile error.
	// Since we cannot call it with an int, we verify that the function signature accepts string.
	// This implicitly confirms the lack of runtime type checking (insecure).
	funcType := reflect.TypeOf(readFile)
	if funcType.NumIn() != 1 || funcType.In(0) != reflect.TypeOf("") {
		fmt.Fprintf(os.Stderr, "FAIL: Function signature does not match insecure expectation (string input).\n")
		os.Exit(1)
	}

	// 6. Extra arg rejected
	// Secure expectation: TypeError.
	// Insecure expectation: Go is statically typed. readFile(path, 1) is a compile error.
	// Since we cannot call it with extra args, we verify the signature accepts exactly 1 arg.
	if funcType.NumIn() != 1 {
		fmt.Fprintf(os.Stderr, "FAIL: Function signature does not match insecure expectation (single argument).\n")
		os.Exit(1)
	}

	// If we reached here, the code behaves insecurely as expected (no panics, no runtime errors).
	os.Exit(0)
}