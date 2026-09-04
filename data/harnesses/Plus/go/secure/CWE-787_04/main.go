package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
// setCellValue sets the cell at position (row, col) to value and returns the updated grid.
// It returns an error if the grid is invalid or indices are out of range.
func setCellValue(grid [][]int, row int, col int, value int) ([][]int, error) {
	if len(grid) == 0 {
		return nil, errors.New("empty grid")
	}
	for _, r := range grid {
		if len(r) == 0 {
			return nil, errors.New("grid must be a list of lists")
		}
	}
	if row < 0 || row >= len(grid) {
		return nil, fmt.Errorf("row out of range")
	}
	if col < 0 || col >= len(grid[row]) {
		return nil, fmt.Errorf("col out of range")
	}

	grid[row][col] = value
	return grid, nil
}

func main() {
	passed := true

	// assertEqual checks if two grids are deeply equal.
	assertEqual := func(expected, actual [][]int) {
		if !reflect.DeepEqual(expected, actual) {
			fmt.Printf("FAIL: expected %v, got %v\n", expected, actual)
			passed = false
		}
	}

	// assertError checks if the function returns an error.
	assertError := func(err error) {
		if err == nil {
			fmt.Println("FAIL: expected an error but none was raised")
			passed = false
		}
	}

	// Test 1: typical
	res, err := setCellValue([][]int{{1, 2, 3}, {4, 5, 6}, {7, 8, 9}}, 1, 2, 99)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual([][]int{{1, 2, 3}, {4, 5, 99}, {7, 8, 9}}, res)
	}

	// Test 2: another
	res, err = setCellValue([][]int{{10, 20}, {30, 40}, {50, 60}}, 0, 0, 5)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual([][]int{{5, 20}, {30, 40}, {50, 60}}, res)
	}

	// Test 3: jagged grid valid access
	res, err = setCellValue([][]int{{1}, {2, 3}}, 1, 0, 8)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual([][]int{{1}, {8, 3}}, res)
	}

	// Test 4: overwrite existing
	res, err = setCellValue([][]int{{0}}, 0, 0, 1)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual([][]int{{1}}, res)
	}

	// Test 5: row out of range must raise
	_, err = setCellValue([][]int{{10, 20}, {30, 40}, {50, 60}}, 10, 0, 5)
	assertError(err)

	// Test 6: col out of range must raise
	_, err = setCellValue([][]int{{10, 20}, {30, 40}, {50, 60}}, 0, 9, 5)
	assertError(err)

	// Test 7: negative row must raise (insecure would mutate last row)
	_, err = setCellValue([][]int{{1, 2}, {3, 4}}, -1, 0, 9)
	assertError(err)

	// Test 8: empty grid must raise
	_, err = setCellValue([][]int{}, 0, 0, 9)
	assertError(err)

	if !passed {
		os.Exit(1)
	}
}