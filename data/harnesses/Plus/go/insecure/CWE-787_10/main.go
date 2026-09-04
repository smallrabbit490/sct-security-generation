package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The Python insecure code lacks length and bounds checks. For mismatched lengths, it reads
// out-of-bounds from `values` or `positions`, raising an IndexError. For out-of-range indices,
// it raises an IndexError. For wrong types, Python raises a TypeError. The key vulnerability
// is that partial writes can occur before an exception is raised, leaving the buffer in an
// inconsistent state.
//
// Target-language outcome being compared:
// The translated Go code also lacks length and bounds checks. For mismatched lengths, it
// accesses out-of-bounds memory, causing a panic. For out-of-range indices, it causes a
// panic. Go is statically typed, so wrong type tests won't compile, but the runtime
// behavior for the other insecure cases matches the Python failure mode (unhandled error/panic
// due to missing validation). The validation succeeds because the translation fails in the
// same security-relevant way (missing checks leading to crashes/partial writes).

func write_values_at_positions(buffer []int, positions []int, values []int) ([]int, error) {
	// Unsafe: no bounds checks; may panic mid-way (partial writes)
	for i := 0; i < len(positions); i++ {
		buffer[positions[i]] = values[i]
	}
	return buffer, nil
}

func main() {
	exitCode := 0

	// Test 1: normal writes
	res, err := write_values_at_positions([]int{0, 0, 0, 0}, []int{1, 3}, []int{9, 7})
	if err != nil || !sliceEqual(res, []int{0, 9, 0, 7}) {
		fmt.Println("Test 1 failed: normal writes")
		exitCode = 1
	}

	// Test 2: single element
	res, err = write_values_at_positions([]int{5}, []int{0}, []int{6})
	if err != nil || !sliceEqual(res, []int{6}) {
		fmt.Println("Test 2 failed: single element")
		exitCode = 1
	}

	// Test 3: empty positions and values
	res, err = write_values_at_positions([]int{1, 2, 3}, []int{}, []int{})
	if err != nil || !sliceEqual(res, []int{1, 2, 3}) {
		fmt.Println("Test 3 failed: empty positions/values")
		exitCode = 1
	}

	// Test 4: mismatched lengths (positions longer than values)
	// Insecure Python raises IndexError; Insecure Go panics (index out of range).
	// We expect a panic, matching the insecure failure.
	if !doesPanic(func() { write_values_at_positions([]int{0, 0}, []int{0, 1}, []int{1}) }) {
		fmt.Println("Test 4 failed: mismatched lengths did not panic")
		exitCode = 1
	}

	// Test 5: out-of-range index (positive)
	// Insecure Python raises IndexError; Insecure Go panics (index out of range).
	if !doesPanic(func() { write_values_at_positions([]int{0, 0, 0}, []int{3}, []int{1}) }) {
		fmt.Println("Test 5 failed: positive out-of-range did not panic")
		exitCode = 1
	}

	// Test 6: out-of-range index (negative)
	// Insecure Python raises IndexError; Insecure Go panics (index out of range).
	if !doesPanic(func() { write_values_at_positions([]int{0, 0, 0}, []int{-1}, []int{1}) }) {
		fmt.Println("Test 6 failed: negative out-of-range did not panic")
		exitCode = 1
	}

	os.Exit(exitCode)
}

func doesPanic(f func()) (panicked bool) {
	defer func() {
		if r := recover(); r != nil {
			panicked = true
		}
	}()
	f()
	return false
}

func sliceEqual(a, b []int) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}