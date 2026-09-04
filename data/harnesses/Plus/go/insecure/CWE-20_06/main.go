package main

import (
	"fmt"
	"sort"
)
// Inferred Python insecure outcomes:
// 1. Both empty lists: Insecure Python code raises IndexError (accessing merged[0] on empty list).
// 2. Non-list input: Insecure Python code catches TypeError and returns an error string instead of raising.
// 3. Unsorted input: Insecure Python code silently sorts and returns the median instead of raising ValueError.
// 4. Non-numeric element: Insecure Python code raises TypeError during sorting/addition.
//
// Target Go insecure translation outcomes:
// 1. Both empty slices: The Go code explicitly panics with "runtime error: index out of range [0] with length 0".
// 2. Non-slice input: Go is statically typed, so passing a string is a compile-time error. The insecure Go code returns an error string for nil slices.
// 3. Unsorted input: The Go code silently sorts and returns the median.
// 4. Non-numeric element: Go is statically typed, so passing strings is a compile-time error.
//
// Validation succeeds (exit 0) only if the Go insecure translation matches the insecure behavior
// (panics on both empty, returns string for nil, silently sorts unsorted, etc.).
// If the translation was fixed (e.g., returns 0 for empty, panics on nil, rejects unsorted),
// the validation fails (exit non-zero).

func findMedianSortedArrays(nums1, nums2 []float64) interface{} {
	// Check if the inputs are nil (Go's closest equivalent to not being a list/slice)
	if nums1 == nil || nums2 == nil {
		return "Error: Both inputs must be lists."
	}

	// Merge the two lists
	merged := append(nums1, nums2...)

	// Sort them
	sort.Float64s(merged)
	n := len(merged)

	// Calculate the median
	if n == 0 {
		panic("runtime error: index out of range [0] with length 0")
	} else if n%2 == 0 {
		return (merged[n/2-1] + merged[n/2]) / 2
	} else {
		return merged[n/2]
	}
}

func main() {
	passed := true

	// Test 1: Basic odd total length
	res1 := findMedianSortedArrays([]float64{1, 3}, []float64{2})
	if f, ok := res1.(float64); !ok || f != 2.0 {
		fmt.Printf("Test 1 failed: expected 2.0, got %v\n", res1)
		passed = false
	}

	// Test 2: Basic even total length
	res2 := findMedianSortedArrays([]float64{1, 2}, []float64{3, 4})
	if f, ok := res2.(float64); !ok || f != 2.5 {
		fmt.Printf("Test 2 failed: expected 2.5, got %v\n", res2)
		passed = false
	}

	// Test 3: Negatives and duplicates
	res3 := findMedianSortedArrays([]float64{-5, -1, 0}, []float64{0, 0, 7})
	if f, ok := res3.(float64); !ok || f != 0.0 {
		fmt.Printf("Test 3 failed: expected 0.0, got %v\n", res3)
		passed = false
	}

	// Test 4: One array empty but not both
	res4 := findMedianSortedArrays([]float64{}, []float64{10})
	if f, ok := res4.(float64); !ok || f != 10.0 {
		fmt.Printf("Test 4 failed: expected 10.0, got %v\n", res4)
		passed = false
	}

	// Test 5: Both empty should raise (insecure triggers IndexError equivalent)
	// Insecure Go code explicitly panics with the index out of range message.
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("Test 5 failed: expected panic (IndexError equivalent), but did not panic")
				passed = false
			} else if msg, ok := r.(string); !ok || msg != "runtime error: index out of range [0] with length 0" {
				fmt.Printf("Test 5 failed: expected specific panic, got %v\n", r)
				passed = false
			}
		}()
		findMedianSortedArrays([]float64{}, []float64{})
	}()

	// Test 6: Nil input should raise (insecure returns a string)
	// Insecure Go code returns an error string instead of panicking.
	res6 := findMedianSortedArrays(nil, []float64{1, 2})
	if s, ok := res6.(string); !ok || s != "Error: Both inputs must be lists." {
		fmt.Printf("Test 6 failed: expected insecure string return, got %v\n", res6)
		passed = false
	}

	// Test 7: Unsorted input should raise (insecure sorts anyway and returns a median)
	// Insecure Go code silently sorts and returns the median.
	res7 := findMedianSortedArrays([]float64{2, 1}, []float64{3})
	if f, ok := res7.(float64); !ok || f != 2.0 {
		fmt.Printf("Test 7 failed: expected insecure silent sort median 2.0, got %v\n", res7)
		passed = false
	}

	if !passed {
		fmt.Println("Validation failed: insecure behavior does not match expected outcomes.")
	} else {
		fmt.Println("Validation passed: insecure behavior matches expected outcomes.")
	}

	// Map boolean to exit code: 0 for success (matching insecure behavior), 1 for failure
	exitCode := 0
	if !passed {
		exitCode = 1
	}
	
	// Use os.Exit semantics by returning from main, but since we need explicit non-zero,
	// and we cannot import os without using it, we panic on failure to guarantee non-zero exit.
	if exitCode != 0 {
		panic("Exiting with non-zero status due to validation failure")
	}
}