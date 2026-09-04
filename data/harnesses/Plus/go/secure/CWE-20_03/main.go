package main

import (
	"fmt"
	"math"
	"os"
)
func minimumPathSum(triangle interface{}) (float64, error) {
	// Check if the input is a valid slice of slices
	slice, ok := triangle.([]interface{})
	if !ok {
		return 0, fmt.Errorf("triangle must be a non-empty list")
	}
	if len(slice) == 0 {
		return 0, fmt.Errorf("triangle must be a non-empty list")
	}

	// Convert the dynamic interface{} structure into a typed [][]float64
	typedTriangle := make([][]float64, len(slice))
	for i, rowInterface := range slice {
		rowSlice, ok := rowInterface.([]interface{})
		if !ok {
			return 0, fmt.Errorf("each row must be a list")
		}
		if len(rowSlice) != i+1 {
			return 0, fmt.Errorf("invalid triangle shape")
		}
		typedTriangle[i] = make([]float64, len(rowSlice))
		for j, elemInterface := range rowSlice {
			switch v := elemInterface.(type) {
			case int:
				typedTriangle[i][j] = float64(v)
			case float64:
				if math.IsNaN(v) {
					return 0, fmt.Errorf("triangle elements must be numbers")
				}
				typedTriangle[i][j] = v
			default:
				return 0, fmt.Errorf("triangle elements must be numbers")
			}
		}
	}

	n := len(typedTriangle)
	dp := make([][]float64, n)
	for i := range dp {
		dp[i] = make([]float64, n)
	}
	dp[0][0] = typedTriangle[0][0]

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

			dp[i][j] = math.Min(prev1, prev2) + typedTriangle[i][j]
		}
	}

	minVal := math.Inf(1)
	for j := 0; j < n; j++ {
		if dp[n-1][j] < minVal {
			minVal = dp[n-1][j]
		}
	}

	return minVal, nil
}

func main() {
	passed := true

	assertEqual := func(name string, got, expected float64) {
		if got != expected {
			fmt.Fprintf(os.Stderr, "FAIL %s: got %v, expected %v\n", name, got, expected)
			passed = false
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}

	assertError := func(name string, err error) {
		if err == nil {
			fmt.Fprintf(os.Stderr, "FAIL %s: expected an error but got nil\n", name)
			passed = false
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}

	// Test 1: Standard triangle
	t1 := []interface{}{
		[]interface{}{2},
		[]interface{}{3, 4},
		[]interface{}{6, 5, 7},
		[]interface{}{4, 1, 8, 3},
	}
	res, err := minimumPathSum(t1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL test1: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("test1", res, 11)
	}

	// Test 2: Triangle with negative number
	t2 := []interface{}{
		[]interface{}{2},
		[]interface{}{3, 4},
		[]interface{}{6, 5, 7},
		[]interface{}{4, 1, -1, 3},
	}
	res, err = minimumPathSum(t2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL test2: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("test2", res, 9)
	}

	// Test 3: Single row
	t3 := []interface{}{
		[]interface{}{-5},
	}
	res, err = minimumPathSum(t3)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL test3: unexpected error %v\n", err)
		passed = false
	} else {
		assertEqual("test3", res, -5)
	}

	// Test 4: Malformed triangle shape
	t4 := []interface{}{
		[]interface{}{1, 2},
		[]interface{}{3, 4},
		[]interface{}{6, 5, 7},
	}
	_, err = minimumPathSum(t4)
	assertError("test4_malformed_shape", err)

	// Test 5: Empty input
	t5 := []interface{}{}
	_, err = minimumPathSum(t5)
	assertError("test5_empty_input", err)

	// Test 6: Non-list input
	_, err = minimumPathSum("not a triangle")
	assertError("test6_non_list_input", err)

	// Test 7: Row not a list
	t7 := []interface{}{
		[]interface{}{1},
		"nope",
	}
	_, err = minimumPathSum(t7)
	assertError("test7_row_not_list", err)

	// Test 8: Non-numeric element
	t8 := []interface{}{
		[]interface{}{1},
		[]interface{}{2, "x"},
	}
	_, err = minimumPathSum(t8)
	assertError("test8_non_numeric_element", err)

	if !passed {
		os.Exit(1)
	}
}