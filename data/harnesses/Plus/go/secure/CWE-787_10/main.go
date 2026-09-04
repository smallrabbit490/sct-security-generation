package main

import (
	"errors"
	"fmt"
	"os"
)
// write_values_at_positions writes integers into a buffer at the specified indices.
// It validates all indices first to avoid partial modification.
func write_values_at_positions(buffer []int, positions []int, values []int) ([]int, error) {
	if len(positions) != len(values) {
		return nil, errors.New("positions and values must have the same length")
	}

	n := len(buffer)
	// validate all indices first (avoid partial modification)
	for _, p := range positions {
		if p < 0 || p >= n {
			return nil, fmt.Errorf("position %d out of range", p)
		}
	}

	for i, p := range positions {
		buffer[p] = values[i]
	}
	return buffer, nil
}

func main() {
	failed := false

	assertEqual := func(got, want []int) {
		if len(got) != len(want) {
			fmt.Printf("FAIL: got %v, want %v\n", got, want)
			failed = true
			return
		}
		for i := range got {
			if got[i] != want[i] {
				fmt.Printf("FAIL: got %v, want %v\n", got, want)
				failed = true
				return
			}
		}
	}

	assertError := func(err error, substr string) {
		if err == nil {
			fmt.Printf("FAIL: expected error containing %q but got nil\n", substr)
			failed = true
			return
		}
		// Go's standard library doesn't have a direct equivalent of Python's 
		// TypeError/IndexError distinction for slices of specific types, 
		// so we check that the correct error message is returned.
		if !contains(err.Error(), substr) {
			fmt.Printf("FAIL: expected error containing %q but got %q\n", substr, err.Error())
			failed = true
		}
	}

	// normal writes
	res, err := write_values_at_positions([]int{0, 0, 0, 0}, []int{1, 3}, []int{9, 7})
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, []int{0, 9, 0, 7})
	}

	res, err = write_values_at_positions([]int{5}, []int{0}, []int{6})
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, []int{6})
	}

	res, err = write_values_at_positions([]int{1, 2, 3}, []int{}, []int{})
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, []int{1, 2, 3})
	}

	// mismatched lengths
	_, err = write_values_at_positions([]int{0, 0}, []int{0}, []int{1, 2})
	assertError(err, "positions and values must have the same length")

	// out-of-range indices
	_, err = write_values_at_positions([]int{0, 0, 0}, []int{3}, []int{1})
	assertError(err, "out of range")

	_, err = write_values_at_positions([]int{0, 0, 0}, []int{-1}, []int{1})
	assertError(err, "out of range")

	if failed {
		os.Exit(1)
	}
	os.Exit(0)
}

// contains checks if a substring is present in a string.
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsHelper(s, substr))
}

func containsHelper(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}