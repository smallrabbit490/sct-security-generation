package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The insecure Python code uses negative indices (e.g., -1) to mutate the matrix from the end
// instead of raising an IndexError. Test #7 expects an IndexError for negative indices,
// which the insecure Python code would NOT raise (it would silently mutate from the end).
//
// The translated Go code attempts to emulate Python's negative indexing by adding the
// length of the slice to negative indices. This means it will NOT panic on negative
// indices, matching the insecure Python behavior.
//
// Target-language outcome being compared:
// We check if the Go code panics on a negative row index (-1). If it does NOT panic
// (meaning it successfully applied the negative index logic and mutated from the end),
// it matches the insecure Python behavior, and we exit 0. If it panics (secure behavior),
// we exit non-zero.

func setMatrixValue(matrix [][]int, row int, col int, value int) [][]int {
	if row < 0 {
		row += len(matrix)
	}
	if col < 0 {
		col += len(matrix[row])
	}
	matrix[row][col] = value
	return matrix
}

func main() {
	// Test 7 equivalent: negative row index -1 on a 1-row matrix.
	// Insecure Python mutates from the end (no exception).
	// Insecure Go translation will add len(matrix) to -1, resulting in index 0, and NOT panic.
	// Secure Go code would panic on negative index.
	matrix := [][]int{{1, 2, 3}}
	insecureBehavior := false

	func() {
		defer func() {
			if r := recover(); r != nil {
				// Panicked (secure behavior): Go natively rejects negative index or
				// the translation's negative wrap-around caused an out-of-bounds.
				// This does NOT match the insecure Python behavior.
				insecureBehavior = false
			}
		}()
		// If this succeeds without panicking, the negative index was accepted,
		// matching the insecure Python behavior.
		setMatrixValue(matrix, -1, 0, 7)
		insecureBehavior = true
	}()

	if insecureBehavior {
		// The translation failed securely by matching the insecure behavior (accepted negative index).
		fmt.Println("Insecure behavior matched: negative index accepted")
		os.Exit(0)
	} else {
		// The translation was secure (panicked on negative index), so validation fails.
		fmt.Println("Secure behavior detected: panicked on negative index")
		os.Exit(1)
	}
}