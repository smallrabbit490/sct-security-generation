package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
// splitAroundPivot splits the list around the element at pivotIndex.
// Elements strictly less than the pivot go to the left slice.
// Elements greater than or equal to the pivot go to the right slice.
func splitAroundPivot(lst []int, pivotIndex int) ([]int, []int, error) {
	if lst == nil {
		return nil, nil, errors.New("lst must be a list")
	}
	if pivotIndex < 0 || pivotIndex >= len(lst) {
		return nil, nil, errors.New("pivot_index out of range")
	}

	pivot := lst[pivotIndex]
	left := make([]int, 0)
	right := make([]int, 0)

	for _, x := range lst {
		if x < pivot {
			left = append(left, x)
		} else {
			right = append(right, x)
		}
	}

	return left, right, nil
}

func main() {
	allPassed := true

	// assertRaises checks that calling splitAroundPivot results in an error
	assertRaises := func(lst []int, pivotIndex int) {
		_, _, err := splitAroundPivot(lst, pivotIndex)
		if err == nil {
			fmt.Printf("FAIL: Expected an error for lst=%v, pivotIndex=%d, but got none\n", lst, pivotIndex)
			allPassed = false
		}
	}

	// assertEqual checks that the function output matches the expected left and right slices
	assertEqual := func(lst []int, pivotIndex int, expectedLeft []int, expectedRight []int) {
		left, right, err := splitAroundPivot(lst, pivotIndex)
		if err != nil {
			fmt.Printf("FAIL: Unexpected error for lst=%v, pivotIndex=%d: %v\n", lst, pivotIndex, err)
			allPassed = false
			return
		}
		if !reflect.DeepEqual(left, expectedLeft) || !reflect.DeepEqual(right, expectedRight) {
			fmt.Printf("FAIL: For lst=%v, pivotIndex=%d, expected (%v, %v), got (%v, %v)\n", lst, pivotIndex, expectedLeft, expectedRight, left, right)
			allPassed = false
		}
	}

	// Test 1: Basic example
	lst1 := []int{4, 7, 2, 9, 1, 5}
	assertEqual(lst1, 2, []int{1}, []int{4, 7, 2, 9, 5})

	// Test 2: Another example
	lst2 := []int{3, 8, 1, 6, 4, 2}
	assertEqual(lst2, 3, []int{3, 1, 4, 2}, []int{8, 6})

	// Test 3: Pivot at the beginning
	lst3 := []int{9, 5, 2, 7, 6, 1}
	assertEqual(lst3, 0, []int{5, 2, 7, 6, 1}, []int{9})

	// Test 4: Out of range pivot index must raise an error
	assertRaises([]int{1, 2, 3}, 5)
	assertRaises([]int{1, 2, 3}, -1)

	// Test 5: Nil list must raise an error (equivalent to Python's TypeError for "not a list")
	assertRaises(nil, 0)

	if allPassed {
		fmt.Println("All tests passed!")
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}