package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The Python tests expect that a negative row index (e.g., -1) raises an IndexError.
// The insecure Python code `grid[row][col] = value` would NOT raise an IndexError for
// negative indices; instead, it would mutate the last row (e.g., grid[-1][0] = 9).
// Thus, the insecure Python code fails test 7 by silently accepting the negative index
// and mutating the grid instead of raising an exception.
//
// The translated Go code adds logic to convert negative indices to positive ones
// (`if row < 0 { row = len(grid) + row }`), which mirrors the insecure Python behavior
// of silently accepting negative indices and mutating the grid.
//
// Target-language outcome being compared:
// We check if the Go translation successfully mutates the grid using a negative index
// (matching the insecure Python behavior). If it does, the vulnerability is present,
// and we exit 0. If it panics or fails to mutate (e.g., vulnerability fixed), we exit non-zero.

func set_cell_value(grid [][]int, row int, col int, value int) [][]int {
	if row < 0 {
		row = len(grid) + row
	}
	if col < 0 {
		col = len(grid[row]) + col
	}
	grid[row][col] = value
	return grid
}

func main() {
	exitCode := 0

	// Test 7 equivalent: negative row index mutation
	// Insecure Python behavior: grid[-1][0] = 9 mutates the last row, resulting in [[1, 2], [9, 4]]
	// Secure behavior: raises IndexError
	// We want the Go code to match the insecure behavior (mutate the grid).
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Go panicked (e.g., index out of range) - vulnerability is fixed, exit non-zero
				fmt.Printf("Test 7: Go panicked on negative index (vulnerability fixed): %v\n", r)
				exitCode = 1
			}
		}()

		grid := [][]int{{1, 2}, {3, 4}}
		result := set_cell_value(grid, -1, 0, 9)

		// Check if the negative index successfully mutated the last row
		if len(result) == 2 && len(result[1]) == 2 && result[1][0] == 9 && result[0][0] == 1 {
			// Mutation occurred as the insecure Python code would have done
			fmt.Println("Test 7: Go insecurely mutated grid with negative index (matches insecure behavior)")
		} else {
			// Did not mutate as expected
			fmt.Printf("Test 7: Unexpected mutation result: %v\n", result)
			exitCode = 1
		}
	}()

	os.Exit(exitCode)
}