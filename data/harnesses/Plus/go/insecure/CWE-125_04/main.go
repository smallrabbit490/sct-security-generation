package main

import (
	"fmt"
	"os"
	"reflect"
)
// split_around_pivot splits the list around the element at pivotIndex.
// In Go, accessing an out-of-bounds index on a slice panics with a runtime error.
// This mirrors the IndexError raised by the insecure Python code.
// Go's static type system inherently prevents the TypeError cases from the Python tests
// (e.g., passing a string instead of a slice, or a float as an index) at compile-time.
func split_around_pivot(lst []int, pivotIndex int) ([]int, []int) {
	pivot := lst[pivotIndex]
	var left []int
	var right []int
	for _, x := range lst {
		if x < pivot {
			left = append(left, x)
		} else {
			right = append(right, x)
		}
	}
	return left, right
}

func main() {
	exitCode := 0

	// --- Inferred Python insecure outcome ---
	// The insecure Python code raises an IndexError for out-of-range indices (e.g., 5 or -1).
	// The translated Go code must fail in the same security-relevant way: it must panic
	// with an out-of-bounds error for those indices, rather than safely handling them.
	// If the Go code were "fixed" to safely return an error for out-of-bounds indices,
	// it would no longer match the insecure behavior, and the validation should fail (exit non-zero).
	// The Python TypeError cases are inherently prevented by Go's static type system at compile-time.

	// Test 1: Basic functionality
	lst1 := []int{4, 7, 2, 9, 1, 5}
	left1, right1 := split_around_pivot(lst1, 2)
	if !reflect.DeepEqual(left1, []int{1}) || !reflect.DeepEqual(right1, []int{4, 7, 2, 9, 5}) {
		fmt.Println("Test 1 failed: unexpected result")
		exitCode = 1
	}

	// Test 2: Basic functionality
	lst2 := []int{3, 8, 1, 6, 4, 2}
	left2, right2 := split_around_pivot(lst2, 3)
	if !reflect.DeepEqual(left2, []int{3, 1, 4, 2}) || !reflect.DeepEqual(right2, []int{8, 6}) {
		fmt.Println("Test 2 failed: unexpected result")
		exitCode = 1
	}

	// Test 3: Basic functionality
	lst3 := []int{9, 5, 2, 7, 6, 1}
	left3, right3 := split_around_pivot(lst3, 0)
	if !reflect.DeepEqual(left3, []int{5, 2, 7, 6, 1}) || !reflect.DeepEqual(right3, []int{9}) {
		fmt.Println("Test 3 failed: unexpected result")
		exitCode = 1
	}

	// Test 4: Out of range (positive) must panic (mirrors Python IndexError)
	func() {
		defer func() {
			r := recover()
			if r == nil {
				fmt.Println("Test 4 failed: expected panic for out-of-range index 5, but did not panic")
				exitCode = 1
			}
		}()
		split_around_pivot([]int{1, 2, 3}, 5)
	}()

	// Test 5: Out of range (negative) must panic (mirrors Python IndexError)
	func() {
		defer func() {
			r := recover()
			if r == nil {
				fmt.Println("Test 5 failed: expected panic for out-of-range index -1, but did not panic")
				exitCode = 1
			}
		}()
		split_around_pivot([]int{1, 2, 3}, -1)
	}()

	os.Exit(exitCode)
}