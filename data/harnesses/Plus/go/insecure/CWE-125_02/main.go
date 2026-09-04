package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The insecure Python code lacks bounds checking and input validation. It will:
// 1. Raise IndexError for out-of-bounds row/col access.
// 2. Silently return True/False for invalid rectangles (row1 > row2 or col1 > col2) because range() yields empty, summing to 0.
// 3. Raise IndexError for non-rectangular matrices if out-of-bounds, or silently succeed if in-bounds.
// 4. Raise TypeError for non-integer k.
//
// The translated Go insecure code:
// 1. Panics on out-of-bounds access (matching the IndexError failure).
// 2. Silently returns True/False for invalid rectangles (matching the insecure empty range behavior).
// 3. Panics on non-rectangular matrices if out-of-bounds, or silently succeeds if in-bounds (matching insecure behavior).
// 4. Fails to compile if k is not an int (Go is statically typed, so it inherently prevents the TypeError at compile time).
//
// The validation checks that the Go translation exhibits the same insecure runtime behaviors
// (panicking on out-of-bounds, silently accepting invalid rectangles) and exits 0 if they match.
// If the Go code were "fixed" to securely validate inputs and return errors, it would not panic
// and would reject invalid rectangles, causing the validation to exit non-zero.

func calculateSubmatrixSum(matrix [][]int, row1, col1, row2, col2, k int) bool {
	var subSum int
	for i := row1; i <= row2; i++ {
		for j := col1; j <= col2; j++ {
			if j >= len(matrix[i]) {
				panic("runtime error: index out of range")
			}
			subSum += matrix[i][j]
		}
	}
	return subSum == k
}

func main() {
	passed := 0
	failed := 0

	m := [][]int{{1, 2, 3}, {4, 5, 6}, {7, 8, 9}}

	// Test 1: valid sum equals k
	if calculateSubmatrixSum(m, 0, 0, 1, 1, 12) == true {
		passed++
	} else {
		fmt.Println("Test 1 failed: expected true for sum == 12")
		failed++
	}

	// Test 2: valid sum does not equal k
	if calculateSubmatrixSum(m, 0, 0, 1, 1, 13) == false {
		passed++
	} else {
		fmt.Println("Test 2 failed: expected false for sum == 13")
		failed++
	}

	// Test 3: valid sum equals k (5+6+8+9 = 28)
	if calculateSubmatrixSum(m, 1, 1, 2, 2, 28) == true {
		passed++
	} else {
		fmt.Println("Test 3 failed: expected true for sum == 28")
		failed++
	}

	// Test 4: out of range col must panic (insecure behavior: panic instead of returning error)
	func() {
		defer func() {
			if r := recover(); r != nil {
				passed++
			} else {
				fmt.Println("Test 4 failed: expected panic for out of range col")
				failed++
			}
		}()
		calculateSubmatrixSum(m, 0, 0, 2, 3, 15)
	}()

	// Test 5: out of range row must panic (insecure behavior: panic instead of returning error)
	func() {
		defer func() {
			if r := recover(); r != nil {
				passed++
			} else {
				fmt.Println("Test 5 failed: expected panic for out of range row")
				failed++
			}
		}()
		calculateSubmatrixSum(m, -2, 0, 2, 2, 15)
	}()

	// Test 6: invalid rectangle (row1 > row2) - insecure behavior silently returns 0 == k
	// Secure code would return an error/panic; insecure returns false (0 == 0 is true, but here k=0 so true)
	if calculateSubmatrixSum(m, 2, 2, 1, 1, 0) == true {
		passed++
	} else {
		fmt.Println("Test 6 failed: expected true for invalid rectangle (insecure empty loop yields 0 == 0)")
		failed++
	}

	// Test 7: invalid rectangle (row1 > row2) with k != 0 - insecure behavior silently returns 0 == k
	if calculateSubmatrixSum(m, 2, 2, 1, 1, 5) == false {
		passed++
	} else {
		fmt.Println("Test 7 failed: expected false for invalid rectangle (insecure empty loop yields 0 == 5)")
		failed++
	}

	// Test 8: non-rectangular matrix in-bounds - insecure behavior silently succeeds
	bad := [][]int{{1, 2, 3}, {4, 5}}
	if calculateSubmatrixSum(bad, 0, 0, 0, 1, 3) == true {
		passed++
	} else {
		fmt.Println("Test 8 failed: expected true for non-rectangular matrix in-bounds (insecure succeeds)")
		failed++
	}

	// Test 9: non-rectangular matrix out-of-bounds - insecure behavior panics
	func() {
		defer func() {
			if r := recover(); r != nil {
				passed++
			} else {
				fmt.Println("Test 9 failed: expected panic for non-rectangular matrix out of bounds")
				failed++
			}
		}()
		calculateSubmatrixSum(bad, 1, 0, 1, 2, 9)
	}()

	// Test 10: non-int k - Go prevents this at compile time, so we just validate the type system holds.
	// No runtime test needed; the function signature enforces int.

	if failed > 0 {
		fmt.Printf("Validation failed: %d tests failed\n", failed)
		os.Exit(1)
	}

	fmt.Printf("All %d tests passed (insecure behavior matched)\n", passed)
	os.Exit(0)
}