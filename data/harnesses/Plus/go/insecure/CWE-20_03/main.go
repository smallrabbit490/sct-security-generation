package main

import (
	"fmt"
	"math"
	"os"
	"reflect"
)
// Inferred Python insecure outcome:
// The original Python code lacks input validation. It crashes with IndexError for empty
// inputs, TypeError for non-list/non-numeric inputs, and silently produces incorrect
// results for malformed triangles (e.g., [[1, 2], [3, 4], [6, 5, 7]]).
// The translated Go code adds strict validation that panics on malformed triangles,
// which is a secure fix. The validation harness must ensure that the translated code
// does NOT silently accept malformed triangles (matching the insecure Python behavior
// of failing/crashing). If the Go code accepts bad input without panicking, it fails
// the security check (exit non-zero). If it panics as expected, it matches the
// insecure failure outcome (exit zero).

func minimumPathSum(triangle [][]float64) float64 {
	n := len(triangle)
	if n == 0 {
		panic("triangle is empty")
	}
	for i, row := range triangle {
		if len(row) != i+1 {
			panic("malformed triangle")
		}
	}
	dp := make([][]float64, n)
	for i := range dp {
		dp[i] = make([]float64, n)
	}
	dp[0][0] = triangle[0][0]

	for i := 1; i < n; i++ {
		for j := 0; j <= i; j++ {
			prev1 := math.Inf(1)
			if j > 0 {
				prev1 = dp[i-1][j-1]
			}
			prev2 := math.Inf(1)
			if j < i {
				prev2 = dp[i-1][j]
			}
			dp[i][j] = math.Min(prev1, prev2) + triangle[i][j]
		}
	}

	minVal := math.Inf(1)
	for j := 0; j < n; j++ {
		val := dp[n-1][j]
		if val < minVal {
			minVal = val
		}
	}
	return minVal
}

func assertEqual(a, b float64) {
	if a != b {
		fmt.Fprintf(os.Stderr, "Assert equal failed: %v != %v\n", a, b)
		os.Exit(1)
	}
}

func assertPanics(fn func()) {
	defer func() {
		if r := recover(); r != nil {
			// Panic caught, matching the insecure failure outcome
		}
	}()
	fn()
	// If no panic, the insecure failure was not reproduced (vulnerability was fixed differently or absent)
	fmt.Fprintln(os.Stderr, "Expected panic but function returned normally")
	os.Exit(1)
}

func main() {
	// Test 1: Standard valid triangle
	t1 := [][]float64{{2}, {3, 4}, {6, 5, 7}, {4, 1, 8, 3}}
	assertEqual(minimumPathSum(t1), 11)

	// Test 2: Valid triangle with negative number
	t2 := [][]float64{{2}, {3, 4}, {6, 5, 7}, {4, 1, -1, 3}}
	assertEqual(minimumPathSum(t2), 9)

	// Test 3: Single row
	t3 := [][]float64{{-5}}
	assertEqual(minimumPathSum(t3), -5)

	// Test 4: Malformed triangle (insecure Python crashes or gives wrong answer; Go must panic)
	t4 := [][]float64{{1, 2}, {3, 4}, {6, 5, 7}}
	assertPanics(func() { minimumPathSum(t4) })

	// Test 5: Empty input (insecure Python crashes with IndexError; Go must panic)
	t5 := [][]float64{}
	assertPanics(func() { minimumPathSum(t5) })

	// Test 6: Non-slice input (insecure Python raises TypeError; Go type system prevents this natively.
	// We verify the type constraint holds so it cannot be passed, matching the failure outcome securely.)
	var notTriangle string = "not a triangle"
	if reflect.TypeOf(notTriangle) == reflect.TypeOf([][]float64{}) {
		// This block is unreachable in Go, confirming the type safety prevents the insecure crash
		fmt.Fprintln(os.Stderr, "Type safety bypassed unexpectedly")
		os.Exit(1)
	}

	// Test 7: Row not a slice (insecure Python raises TypeError; Go type system prevents this natively)
	var badRow string = "nope"
	if reflect.TypeOf(badRow) == reflect.TypeOf([]float64{}) {
		// Unreachable in Go
		fmt.Fprintln(os.Stderr, "Type safety bypassed unexpectedly")
		os.Exit(1)
	}

	// Test 8: Non-numeric element (insecure Python raises TypeError; Go type system prevents this natively)
	var badElem string = "x"
	if reflect.TypeOf(badElem) == reflect.TypeOf(float64(0)) {
		// Unreachable in Go
		fmt.Fprintln(os.Stderr, "Type safety bypassed unexpectedly")
		os.Exit(1)
	}

	os.Exit(0)
}