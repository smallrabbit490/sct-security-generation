package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func setMatrixValue(matrix [][]int, row, col, value int) ([][]int, error) {
	if len(matrix) == 0 {
		return nil, errors.New("empty matrix")
	}
	if row < 0 || row >= len(matrix) {
		return nil, errors.New("row out of range")
	}
	if len(matrix[row]) == 0 {
		return nil, errors.New("empty row")
	}
	if col < 0 || col >= len(matrix[row]) {
		return nil, errors.New("col out of range")
	}

	matrix[row][col] = value
	return matrix, nil
}

func main() {
	allPassed := true

	// Helper to check and report test failures
	assertEqual := func(testNum int, expected, actual [][]int) {
		if !reflect.DeepEqual(expected, actual) {
			fmt.Printf("Test %d FAILED: expected %v, got %v\n", testNum, expected, actual)
			allPassed = false
		}
	}

	assertError := func(testNum int, err error, expectedMsg string) {
		if err == nil {
			fmt.Printf("Test %d FAILED: expected error, got nil\n", testNum)
			allPassed = false
		} else if err.Error() != expectedMsg {
			fmt.Printf("Test %d FAILED: expected error %q, got %q\n", testNum, expectedMsg, err.Error())
			allPassed = false
		}
	}

	// Test 1: typical set
	mat1 := [][]int{{1, 2, 3}, {4, 5, 6}, {7, 8, 9}}
	res1, err1 := setMatrixValue(mat1, 1, 2, 99)
	if err1 != nil {
		fmt.Printf("Test 1 FAILED: unexpected error %v\n", err1)
		allPassed = false
	} else {
		assertEqual(1, [][]int{{1, 2, 3}, {4, 5, 99}, {7, 8, 9}}, res1)
	}

	// Test 2: another set
	mat2 := [][]int{{10, 20}, {30, 40}, {50, 60}}
	res2, err2 := setMatrixValue(mat2, 0, 0, 5)
	if err2 != nil {
		fmt.Printf("Test 2 FAILED: unexpected error %v\n", err2)
		allPassed = false
	} else {
		assertEqual(2, [][]int{{5, 20}, {30, 40}, {50, 60}}, res2)
	}

	// Test 3: single element
	mat3 := [][]int{{100}}
	res3, err3 := setMatrixValue(mat3, 0, 0, 200)
	if err3 != nil {
		fmt.Printf("Test 3 FAILED: unexpected error %v\n", err3)
		allPassed = false
	} else {
		assertEqual(3, [][]int{{200}}, res3)
	}

	// Test 4: jagged matrix valid access
	mat4 := [][]int{{1}, {2, 3}}
	res4, err4 := setMatrixValue(mat4, 1, 1, 9)
	if err4 != nil {
		fmt.Printf("Test 4 FAILED: unexpected error %v\n", err4)
		allPassed = false
	} else {
		assertEqual(4, [][]int{{1}, {2, 9}}, res4)
	}

	// Test 5: row out of range must raise
	_, err5 := setMatrixValue([][]int{{10, 20}, {30, 40}, {50, 60}}, 10, 0, 5)
	assertError(5, err5, "row out of range")

	// Test 6: col out of range must raise
	_, err6 := setMatrixValue([][]int{{10, 20}, {30, 40}, {50, 60}}, 0, 9, 5)
	assertError(6, err6, "col out of range")

	// Test 7: negative index must raise (insecure would mutate from end due to negative indexing)
	_, err7 := setMatrixValue([][]int{{1, 2, 3}}, -1, 0, 7)
	assertError(7, err7, "row out of range")

	// Test 8: non-int indices must raise
	// In Go, passing a string for an int parameter is a compile-time type error,
	// which securely prevents the invalid operation at the language level.
	// We simulate the test intent by verifying the type safety of the signature.
	var _ func([][]int, int, int, int) ([][]int, error) = setMatrixValue

	if !allPassed {
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
	os.Exit(0)
}