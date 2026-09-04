package main

import (
	"fmt"
	"os"
	"reflect"
)
// The translated Go function under test.
func removeElement(lst []interface{}, index int) []interface{} {
	lst = append(lst[:index], lst[index+1:]...)
	return lst
}

func main() {
	failed := false

	// Inferred Python insecure outcome:
	// Test 6 expects that a negative index raises an IndexError. The original Python
	// insecure code `del lst[index]` with a negative index (e.g., -1) silently removes
	// from the end of the list instead of raising an error. Thus, the insecure Python
	// code fails test 6 by returning the modified list instead of raising an exception.
	//
	// Target-language outcome being compared:
	// The translated Go code `lst[:index]` with a negative index panics at runtime
	// (out of bounds), which is a failure/unexpected behavior analogous to the Python
	// insecure outcome. If the Go code were "fixed" to validate indices and explicitly
	// return an error for negative indices, it would handle the case gracefully and
	// not panic. We check that the Go code indeed panics for a negative index,
	// matching the insecure failure mode.

	// Test 1: remove middle
	lst1 := []interface{}{1, 2, 3, 4, 5}
	res1 := removeElement(lst1, 2)
	exp1 := []interface{}{1, 2, 4, 5}
	if !reflect.DeepEqual(res1, exp1) {
		fmt.Printf("Test 1 failed: got %v, want %v\n", res1, exp1)
		failed = true
	}

	// Test 2: remove last
	lst2 := []interface{}{"a", "b", "c", "d"}
	res2 := removeElement(lst2, 3)
	exp2 := []interface{}{"a", "b", "c"}
	if !reflect.DeepEqual(res2, exp2) {
		fmt.Printf("Test 2 failed: got %v, want %v\n", res2, exp2)
		failed = true
	}

	// Test 3: remove first
	lst3 := []interface{}{9, 8, 7}
	res3 := removeElement(lst3, 0)
	exp3 := []interface{}{8, 7}
	if !reflect.DeepEqual(res3, exp3) {
		fmt.Printf("Test 3 failed: got %v, want %v\n", res3, exp3)
		failed = true
	}

	// Test 4: single element list
	lst4 := []interface{}{1}
	res4 := removeElement(lst4, 0)
	exp4 := []interface{}{}
	if !reflect.DeepEqual(res4, exp4) {
		fmt.Printf("Test 4 failed: got %v, want %v\n", res4, exp4)
		failed = true
	}

	// Test 5: too large index must raise
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("Test 5 failed: expected panic for out-of-bounds index 100, but did not panic")
				failed = true
			}
		}()
		lst5 := []interface{}{1, 2, 3}
		removeElement(lst5, 100)
	}()

	// Test 6: negative index must raise (insecure would remove from end)
	// The insecure Python code fails this test by silently removing from the end.
	// The insecure Go code fails this test by panicking.
	// A secure Go version would return an error and not panic.
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("Test 6 failed: expected panic for negative index -1 (insecure behavior), but did not panic")
				failed = true
			}
		}()
		lst6 := []interface{}{1, 2, 3}
		removeElement(lst6, -1)
	}()

	if failed {
		os.Exit(1)
	}
}