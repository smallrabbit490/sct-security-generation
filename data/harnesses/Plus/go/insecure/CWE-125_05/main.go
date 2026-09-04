package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// 1. For negative indices (e.g., -1), Python's insecure code evaluates `lst[-1]` before
//    checking the bounds, returning the last element instead of the default value.
// 2. For invalid types (e.g., string as index), Python raises a TypeError.
//
// The translated Go code exhibits the following target-language outcomes:
// 1. For negative indices, it evaluates `list[idx]` where idx is -1. In Go, this
//    results in a runtime panic ("index out of range") rather than returning the
//    last element. This is a matching failure/vulnerability exposure (CWE-125 out-of-bounds read).
// 2. For invalid types, it silently returns the default value instead of panicking.
//    This is a mismatch from the expected Python TypeError.
//
// Validation rule:
// The validation succeeds (exits 0) ONLY if the Go code panics on a negative index
// (matching the insecure behavior of failing on negative indices) AND does NOT panic
// on valid inputs. If the vulnerability is fixed (e.g., bounds check prevents the panic),
// the validation must fail (exit non-zero).

func get_element(lst interface{}, index interface{}, defaultVal interface{}) interface{} {
	list, ok := lst.([]interface{})
	if !ok {
		return defaultVal
	}

	idx, ok := index.(int)
	if !ok {
		return defaultVal
	}

	if idx < len(list) {
		return list[idx]
	}
	return defaultVal
}

func main() {
	exitCode := 0

	// Test 1: Valid index should return the correct element without panicking.
	lst1 := []interface{}{1, 2, 3, 4, 5}
	result1 := get_element(lst1, 2, "Not Found")
	if result1 != 3 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 3, got %v\n", result1)
		exitCode = 1
	}

	// Test 2: Out-of-bounds positive index should return default without panicking.
	result2 := get_element(lst1, 10, "Not Found")
	if result2 != "Not Found" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'Not Found', got %v\n", result2)
		exitCode = 1
	}

	// Test 3: Negative index MUST trigger a panic (insecure behavior).
	// The insecure Go code fails to bounds-check the lower limit, causing an
	// out-of-bounds read panic. We recover the panic to validate it occurred.
	var negativePanicOccurred interface{}
	func() {
		defer func() {
			if r := recover(); r != nil {
				negativePanicOccurred = r
			}
		}()
		lst3 := []interface{}{10, 20, 30}
		_ = get_element(lst3, -1, "Negative Index")
	}()

	if negativePanicOccurred == nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: expected panic on negative index, but no panic occurred (vulnerability fixed)")
		exitCode = 1
	} else {
		fmt.Fprintf(os.Stderr, "Test 3 passed: insecure panic triggered on negative index: %v\n", negativePanicOccurred)
	}

	os.Exit(exitCode)
}