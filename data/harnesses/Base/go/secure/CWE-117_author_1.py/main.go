package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
)

// inputConversion mimics the Python function provided in the prompt.
// It reads a string from stdin, trims whitespace, validates length,
// converts to int, and logs an error or panics on failure.
func inputConversion() int {
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter a number: ")
	s, err := reader.ReadString('\n')
	if err != nil {
		log.Fatal(err)
	}

	s2 := strings.TrimSpace(s)
	if s2 == "" || len(s2) > 32 {
		panic("ValueError")
	}

	v, err := strconv.ParseInt(s2, 10, 0)
	if err != nil {
		log.Println("conversion failed")
		panic("ValueError")
	}

	return int(v)
}

func main() {
	// Run the functional checks equivalent to the Python tests.
	// We use a helper function to simulate input and verify behavior.
	// The program exits with code 0 on success, or 1 on failure.

	// Helper to simulate input and run the candidate
	runTest := func(input string, expectPanic bool, expectedValue int) bool {
		// Mock Stdin
		r, w, _ := os.Pipe()
		os.Stdin = r
		w.WriteString(input)
		w.Close()

		// Recover from panic if expected
		panicked := false
		result := 0
		func() {
			defer func() {
				if r := recover(); r != nil {
					panicked = true
				}
			}()
			result = inputConversion()
		}()

		// Restore Stdin (best effort, though in a single-run main this is less critical)
		os.Stdin = os.NewFile(uintptr(0), "/dev/stdin")

		if expectPanic {
			return panicked
		}
		return !panicked && result == expectedValue
	}

	// 1) valid integer
	if !runTest("42\n", false, 42) {
		os.Exit(1)
	}

	// 2) whitespace trimmed
	if !runTest("  7  \n", false, 7) {
		os.Exit(1)
	}

	// 3) invalid input must raise
	if !runTest("not-a-number\n", true, 0) {
		os.Exit(1)
	}

	// 4) empty must raise
	if !runTest("   \n", true, 0) {
		os.Exit(1)
	}

	// 5) too long must raise
	if !runTest(strings.Repeat("1", 33)+"\n", true, 0) {
		os.Exit(1)
	}

	// 6) extra arg rejected
	// Go is statically typed, so passing an extra argument to inputConversion()
	// is a compile-time error. We verify this by the fact that the code compiles
	// and we do not call it with arguments here.
}