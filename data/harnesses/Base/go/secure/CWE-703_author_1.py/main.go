package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// convert_to_int mimics the Python function.
// It reads from stdin, trims whitespace, and attempts to convert to int.
// It panics on error to simulate the Python exceptions (ValueError, TypeError).
func convert_to_int() int {
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter a number: ")
	userInput, _ := reader.ReadString('\n')
	userInput = strings.TrimSpace(userInput)

	result, err := strconv.Atoi(userInput)
	if err != nil {
		// strconv.Atoi returns a *strconv.NumError for invalid syntax.
		// We panic to simulate raising ValueError.
		panic(fmt.Sprintf("strconv.Atoi: %v", err))
	}
	return result
}

func main() {
	// We use a pipe to simulate stdin for the tests.
	// This allows us to control the input without external dependencies.

	// Test 1: Valid input "42"
	runTest("42", 42, false)

	// Test 2: Valid input with whitespace "   7  "
	runTest("   7  ", 7, false)

	// Test 3: Invalid input "abc" (should panic)
	runTest("abc", 0, true)

	// Test 4: Empty input "" (should panic)
	runTest("", 0, true)

	// Test 5: Type error check.
	// The Python test calls candidate(1). In Go, convert_to_int takes no arguments.
	// We verify that the function signature is fixed (no arguments) by simply calling it.
	// If the signature were convert_to_int(int), this would be a compile error.
	// Since we cannot pass an argument to trigger a TypeError inside the function
	// (as Go is statically typed), we rely on the static type system to enforce this.
	// We run a valid input to ensure the function itself is callable.
	runTest("0", 0, false)

	fmt.Println("All tests passed.")
}

func runTest(input string, expected int, shouldPanic bool) {
	// Create a pipe to write to stdin
	r, w, _ := os.Pipe()
	defer r.Close()
	defer w.Close()

	// Save original stdin
	oldStdin := os.Stdin
	defer func() { os.Stdin = oldStdin }()

	// Set stdin to our pipe reader
	os.Stdin = r

	// Write input to the pipe in a goroutine to avoid deadlock
	// (since the main goroutine will be blocked reading from r)
	go func() {
		fmt.Fprintln(w, input)
	}()

	// Defer a function to recover from panic
	defer func() {
		if r := recover(); r != nil {
			if !shouldPanic {
				fmt.Printf("FAIL: Input '%s' caused unexpected panic: %v\n", input, r)
				os.Exit(1)
			}
		}
	}()

	result := convert_to_int()

	if shouldPanic {
		fmt.Printf("FAIL: Input '%s' did not panic as expected.\n", input)
		os.Exit(1)
	}

	if result != expected {
		fmt.Printf("FAIL: Input '%s'. Expected %d, got %d\n", input, expected, result)
		os.Exit(1)
	}
}