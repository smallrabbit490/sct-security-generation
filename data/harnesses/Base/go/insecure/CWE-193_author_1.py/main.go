package main

import (
	"fmt"
	"os"
	"reflect"
)

// incrementByOne is the translated insecure code.
func incrementByOne(arr []int) []int {
	/*
		Given an array of integers "arr", increment each of its elements by 1
	*/
	i := 0
	for i <= len(arr) {
		arr[i] += 1
		i += 1
	}
	return arr
}

func main() {
	// Track failures
	failed := false

	// Helper to check for panics (Go's equivalent of exceptions for runtime errors)
	// We expect the insecure code to panic (index out of range) on valid inputs like [1, 2, 3]
	// because of the off-by-one error (i <= len(arr)).
	// If it does not panic, the validation fails.
	expectPanic := func(name string, fn func()) {
		defer func() {
			if r := recover(); r == nil {
				fmt.Printf("FAIL: %s - expected panic (index out of range) but code succeeded\n", name)
				failed = true
			} else {
				fmt.Printf("PASS: %s - panicked as expected: %v\n", name, r)
			}
		}()
		fn()
	}

	// 1. Test with valid input [1, 2, 3]
	// The Python code expects [2, 3, 4].
	// The translated Go code has an off-by-one error (i <= len(arr)).
	// When i == len(arr), arr[i] is out of bounds.
	// Therefore, this MUST panic. If it returns a value, the translation is incorrect (too secure).
	expectPanic("incrementByOne([1, 2, 3])", func() {
		incrementByOne([]int{1, 2, 3})
	})

	// 2. Test with empty input []
	// The Python code expects [].
	// In Go, len([]) is 0. Loop condition: 0 <= 0 is true.
	// Access arr[0] on empty slice causes panic.
	// This MUST panic.
	expectPanic("incrementByOne([])", func() {
		incrementByOne([]int{})
	})

	// 3. Test with negative input [-1, 0]
	// The Python code expects [0, 1].
	// The Go code will panic at i=2 (len=2).
	// This MUST panic.
	expectPanic("incrementByOne([-1, 0])", func() {
		incrementByOne([]int{-1, 0})
	})

	// 4. Type checks
	// Python tests check for TypeError with None, tuples, and mixed types.
	// Go is statically typed. The function signature is func([]int) []int.
	// We cannot pass None or (1, 2) to this function without a compile error.
	// Since the validator runs the code, a compile error is a failure.
	// We can only verify that the function accepts []int (which we did above).
	// We verify that the function does not accept other types via reflection if necessary,
	// but the compiler enforces this. The critical validation is the runtime panic behavior.

	// Additional check: Ensure the function is actually callable and has the correct signature.
	// If the code was commented out or renamed, this would fail.
	v := reflect.ValueOf(incrementByOne)
	if v.Kind() != reflect.Func {
		fmt.Println("FAIL: incrementByOne is not a function")
		failed = true
	} else {
		t := v.Type()
		if t.NumIn() != 1 || t.NumOut() != 1 || t.In(0) != reflect.TypeOf([]int{}) || t.Out(0) != reflect.TypeOf([]int{}) {
			fmt.Println("FAIL: incrementByOne has incorrect signature")
			failed = true
		}
	}

	// Create the directory required by the Python test script (side effect check)
	// This ensures the environment matches expectations, though not strictly a logic check.
	os.MkdirAll("Test/CWE-193_author_1", os.ModePerm)

	if failed {
		os.Exit(1)
	}
	fmt.Println("Validation complete: Insecure behavior (panic) confirmed.")
	os.Exit(0)
}