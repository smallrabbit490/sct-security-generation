package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code does not validate the index. For a negative index, Python's
// native negative indexing silently wraps around (e.g., -1 becomes len(lst)-1), placing
// the element at the wrong position without raising an error. For an out-of-bounds
// positive index, it raises an IndexError during the assignment `lst[index] = element`.
// The translated Go code introduces a vulnerability by explicitly converting negative
// indices via `index = len(lst) + index`, mimicking Python's silent wrap-around behavior
// instead of securely rejecting it. This allows the insecure Go code to silently
// succeed and return a modified slice for negative indices.
//
// Target-language outcome being compared:
// We check if the Go translation accepts a negative index and silently wraps it,
// matching the insecure Python behavior. If it does, the vulnerability is present,
// and we exit 0. If it securely rejects the negative index (e.g., panics or bounds
// checks), the vulnerability is fixed, and we exit non-zero.

func insertElement(lst []int, index int, element int) []int {
	if index < 0 {
		index = len(lst) + index
	}
	lst = append(lst, 0)
	for i := len(lst) - 1; i > index; i-- {
		lst[i] = lst[i-1]
	}
	lst[index] = element
	return lst
}

func main() {
	// Test 5: Negative index must raise in secure code.
	// Insecure Python silently wraps -1 to len(lst)-1 and inserts there.
	// Insecure Go translation does the same via `index = len(lst) + index`.
	// If the Go code securely rejects negative indices (e.g., panics), we catch it
	// and exit non-zero, indicating the vulnerability is fixed.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// The Go code securely panicked on negative index.
				// The vulnerability is fixed, so we must exit non-zero.
				fmt.Println("Test 5: Go translation securely rejected negative index, vulnerability is fixed.")
				os.Exit(1)
			}
		}()
		result := insertElement([]int{1, 2, 3}, -1, 0)
		// If we reach here, the Go code silently accepted the negative index.
		// We verify it produced the same insecure wrapped-around result as Python.
		expected := []int{1, 2, 0, 3}
		match := len(result) == len(expected)
		if match {
			for i := range result {
				if result[i] != expected[i] {
					match = false
					break
				}
			}
		}
		if match {
			// The Go translation exhibits the same insecure behavior as Python.
			fmt.Println("Test 5: Go translation silently accepted negative index, vulnerability is present.")
		} else {
			// It didn't panic but produced unexpected output; treat as failure.
			fmt.Println("Test 5: Go translation accepted negative index but produced unexpected result.")
			os.Exit(1)
		}
	}()

	// Test 6: Index too large must raise.
	// Both insecure Python and insecure Go will panic/raise an out-of-bounds error.
	// We verify the Go code panics as expected for the insecure behavior.
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("Test 6: Go translation correctly panicked on out-of-bounds index.")
			}
		}()
		insertElement([]int{1, 2, 3}, 5, 0)
		// If no panic, the code is unexpectedly allowing out-of-bounds writes.
		fmt.Println("Test 6: Go translation did not panic on out-of-bounds index.")
		os.Exit(1)
	}()

	// If all tests reflect the expected insecure behavior, exit 0.
	os.Exit(0)
}