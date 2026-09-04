package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func calculate_submatrix_sum(matrix [][]int, row1, col1, row2, col2, k int) (bool, error) {
	if matrix == nil || len(matrix) == 0 {
		return false, errors.New("matrix must be a non-empty list of lists")
	}
	for _, r := range matrix {
		if r == nil || len(r) == 0 {
			return false, errors.New("matrix rows must be non-empty")
		}
	}
	width := len(matrix[0])
	for _, r := range matrix {
		if len(r) != width {
			return false, errors.New("matrix must be rectangular")
		}
	}

	for _, r := range matrix {
		for _, x := range r {
			if reflect.TypeOf(x).Kind() != reflect.Int {
				return false, errors.New("matrix elements must be integers")
			}
		}
	}

	h := len(matrix)
	w := width

	if row1 < 0 || col1 < 0 || row2 < 0 || col2 < 0 {
		return false, errors.New("coordinates out of range")
	}
	if row1 > row2 || col1 > col2 {
		return false, errors.New("invalid rectangle")
	}
	if row2 >= h || col2 >= w {
		return false, errors.New("coordinates out of range")
	}

	total := 0
	for i := row1; i <= row2; i++ {
		for j := col1; j <= col2; j++ {
			total += matrix[i][j]
		}
	}
	return total == k, nil
}

func main() {
	failed := false

	assertBool := func(desc string, got, want bool) {
		if got != want {
			fmt.Fprintf(os.Stderr, "FAIL %s: got %v, want %v\n", desc, got, want)
			failed = true
		} else {
			fmt.Printf("PASS %s\n", desc)
		}
	}

	assertError := func(desc string, err error) {
		if err == nil {
			fmt.Fprintf(os.Stderr, "FAIL %s: expected an error but got nil\n", desc)
			failed = true
		} else {
			fmt.Printf("PASS %s: got expected error (%v)\n", desc, err)
		}
	}

	m := [][]int{{1, 2, 3}, {4, 5, 6}, {7, 8, 9}}

	// valid
	res, err := calculate_submatrix_sum(m, 0, 0, 1, 1, 12)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL valid 1: unexpected error %v\n", err)
		failed = true
	} else {
		assertBool("valid 1 (sum==12)", res, true)
	}

	res, err = calculate_submatrix_sum(m, 0, 0, 1, 1, 13)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL valid 2: unexpected error %v\n", err)
		failed = true
	} else {
		assertBool("valid 2 (sum==13)", res, false)
	}

	res, err = calculate_submatrix_sum(m, 1, 1, 2, 2, 28)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL valid 3: unexpected error %v\n", err)
		failed = true
	} else {
		assertBool("valid 3 (sum==28)", res, true)
	}

	// out of range must raise
	_, err = calculate_submatrix_sum(m, 0, 0, 2, 3, 15)
	assertError("out of range (col2 >= w)", err)

	_, err = calculate_submatrix_sum(m, -2, 0, 2, 2, 15)
	assertError("out of range (row1 < 0)", err)

	// invalid rectangle must raise
	_, err = calculate_submatrix_sum(m, 2, 2, 1, 1, 0)
	assertError("invalid rectangle", err)

	// non-rectangular matrix must raise
	bad := [][]int{{1, 2, 3}, {4, 5}}
	_, err = calculate_submatrix_sum(bad, 0, 0, 0, 1, 3)
	assertError("non-rectangular matrix", err)

	// non-int k must raise (Go enforces int type at compile time, so we simulate
	// the Python test's intent by passing a string to an interface{} wrapper)
	calculateSubmatrixSumAny := func(matrixAny interface{}, row1, col1, row2, col2 int, kAny interface{}) (bool, error) {
		kInt, ok := kAny.(int)
		if !ok {
			return false, errors.New("k must be an integer")
		}
		matInt, ok := matrixAny.([][]int)
		if !ok {
			return false, errors.New("matrix must be a non-empty list of lists of integers")
		}
		return calculate_submatrix_sum(matInt, row1, col1, row2, col2, kInt)
	}

	_, err = calculateSubmatrixSumAny(m, 0, 0, 0, 0, "1")
	assertError("non-int k", err)

	if failed {
		fmt.Println("OVERALL: FAIL")
		os.Exit(1)
	}
	fmt.Println("OVERALL: PASS")
}