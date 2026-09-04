package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
)

func convertToInt() int {
	scanner := bufio.NewScanner(os.Stdin)
	attempts := 0
	for attempts < 2 {
		fmt.Print("Enter a number: ")
		if !scanner.Scan() {
			// Handle EOF or read error
			panic(scanner.Err())
		}
		userInput := scanner.Text()
		// In Go, scanner.Text() always returns a string, so no type check needed
		val, err := strconv.Atoi(userInput)
		if err == nil {
			return val
		}
		attempts++
	}
	panic("ValueError")
}

func main() {
	// The problem requires a self-contained validation program.
	// We simulate the Python tests here to ensure the logic is correct.
	// If any test fails, we exit with a non-zero code.

	// Helper to simulate input
	type testCase struct {
		inputs []string
		pass   bool
	}

	tests := []testCase{
		{inputs: []string{"x", "10"}, pass: true}, // Should succeed on second attempt
		{inputs: []string{"a", "b"}, pass: false}, // Should fail (ValueError)
	}

	for _, tc := range tests {
		// Create a pipe to simulate stdin
		r, w, _ := os.Pipe()
		defer r.Close()
		defer w.Close()

		// Write inputs to the pipe
		for _, s := range tc.inputs {
			w.WriteString(s + "\n")
		}
		w.Close()

		// Save original stdin and replace with pipe reader
		oldStdin := os.Stdin
		os.Stdin = r
		defer func() { os.Stdin = oldStdin }()

		// Recover from panics to check result
		func() {
			defer func() {
				r := recover()
				if tc.pass {
					// Expected success, but got panic
					if r != nil {
						fmt.Printf("FAIL: Expected success but got panic: %v\n", r)
						os.Exit(1)
					}
				} else {
					// Expected failure (ValueError panic)
					if r == nil {
						fmt.Println("FAIL: Expected panic (ValueError) but function returned successfully")
						os.Exit(1)
					}
					if r != "ValueError" {
						fmt.Printf("FAIL: Expected panic 'ValueError' but got: %v\n", r)
						os.Exit(1)
					}
				}
			}()

			convertToInt()
		}()
	}

	// Test for TypeError equivalent is not applicable in Go as scanner.Text() always returns string.
	// The Python test `assert_raises(candidate, 1, exc_types=(TypeError,))` checks if the function
	// raises TypeError when called with an int. In Go, `convertToInt` takes no arguments,
	// so this specific check is handled by the type system at compile time.

	fmt.Println("All tests passed.")
}