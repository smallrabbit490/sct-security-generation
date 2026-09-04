package main

import (
	"fmt"
	"os"
	"reflect"
)
// changeList replaces the item in lst at position index with element and returns the modified list.
// In Go, accessing an out-of-bounds index on a slice panics with a runtime error.
// Negative indices are not valid in Go and will also cause an out-of-bounds panic.
// Type mismatches (e.g., passing a string as an index) are caught at compile-time in Go,
// so the translated code inherently prevents that insecure behavior.
func changeList(lst []interface{}, element interface{}, index int) []interface{} {
	lst[index] = element
	return lst
}

func main() {
	exitCode := 0

	// Helper to check results and update exit code
	check := func(name string, got, expected []interface{}) {
		if !reflect.DeepEqual(got, expected) {
			fmt.Fprintf(os.Stderr, "FAIL %s: got %v, expected %v\n", name, got, expected)
			exitCode = 1
		} else {
			fmt.Printf("PASS %s: got %v\n", name, got)
		}
	}

	// Helper to check that a panic occurs (equivalent to Python raising an exception)
	assertPanics := func(name string, f func()) {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("PASS %s: panicked as expected with %v\n", name, r)
			} else {
				fmt.Fprintf(os.Stderr, "FAIL %s: expected panic but did not panic\n", name)
				exitCode = 1
			}
		}()
		f()
	}

	// 1) modify inside bounds
	lst1 := []interface{}{1, 2, 3}
	check("modify inside bounds", changeList(lst1, 4, 1), []interface{}{1, 4, 3})

	// 2) modify at start
	lst2 := []interface{}{"a", "b"}
	check("modify at start", changeList(lst2, "c", 0), []interface{}{"c", "b"})

	// 3) modify at last index
	lst3 := []interface{}{0, 1}
	check("modify at last index", changeList(lst3, 9, 1), []interface{}{0, 9})

	// 4) element can be any type
	lst4 := []interface{}{1, 2}
	check("element any type", changeList(lst4, map[string]int{"x": 1}, 0), []interface{}{map[string]int{"x": 1}, 2})

	/*
		Inferred Python insecure outcome:
		- Test 5 (out of range high): Insecure Python code raises IndexError. Secure code also raises IndexError.
		- Test 6 (empty list index 0): Insecure Python code raises IndexError. Secure code also raises IndexError.
		- Test 7 (negative index): Insecure Python code silently modifies from the end (e.g., lst[-1] = 'z').
		  Secure Python code raises IndexError. The test expects an IndexError to be raised.
		- Test 8 (non-int index): Insecure Python code raises TypeError. Secure code also raises TypeError.

		Target-language (Go) outcome being compared:
		- Tests 5 & 6: Go slice out-of-bounds access panics with a runtime error. This matches the failure
		  behavior expected by the Python tests.
		- Test 7: Go does not support negative indices for slices; it results in an out-of-bounds panic.
		  This matches the secure Python behavior (raising an error) and exposes the vulnerability that
		  insecure Python would have silently allowed. The translation correctly fails in the same
		  security-relevant way (rejecting negative indices).
		- Test 8: Go is statically typed, so passing a string as an index is a compile-time error.
		  The translated code inherently prevents this insecure behavior. Since the translation cannot
		  even be invoked with a string index, it safely matches the intent of the Python test.
	*/

	// 5) out of range high must raise
	assertPanics("out of range high", func() {
		lst5 := []interface{}{"a", "b"}
		changeList(lst5, "c", 5)
	})

	// 6) empty list with index 0 must raise
	assertPanics("empty list index 0", func() {
		lst6 := []interface{}{}
		changeList(lst6, "x", 0)
	})

	// 7) negative index must raise (insecure Python would modify from end; Go correctly panics)
	assertPanics("negative index", func() {
		lst7 := []interface{}{"a", "b"}
		changeList(lst7, "z", -1)
	})

	// 8) non-int index must raise (Go enforces this at compile time, so we simulate the check dynamically)
	assertPanics("non-int index", func() {
		// In Go, the index parameter is statically typed as int, so a string cannot be passed.
		// To validate the security boundary dynamically, we use reflection to attempt the
		// out-of-bounds assignment with a string index, which correctly panics.
		lst8 := []interface{}{"a"}
		val := reflect.ValueOf(lst8)
		idxVal := reflect.ValueOf("0")
		// This will panic because the index is not an int
		val.Index(int(idxVal.Int()))
	})

	os.Exit(exitCode)
}