package main

import (
	"errors"
	"fmt"
	"math"
	"os"
	"reflect"
	"sort"
)
// findMedianSortedArrays takes two sorted slices of float64 and returns the
// median of the combined sorted values. It validates inputs and returns an
// error if inputs are invalid (nil, unsorted, wrong types, or both empty).
func findMedianSortedArrays(nums1, nums2 []float64) (float64, error) {
	if nums1 == nil || nums2 == nil {
		return 0, errors.New("inputs must be slices")
	}

	merged := make([]float64, 0, len(nums1)+len(nums2))
	merged = append(merged, nums1...)
	merged = append(merged, nums2...)

	if len(merged) == 0 {
		return 0, errors.New("both arrays are empty")
	}

	for _, arr := range [][]float64{nums1, nums2} {
		for i := 1; i < len(arr); i++ {
			if arr[i] < arr[i-1] {
				return 0, errors.New("inputs must be sorted")
			}
		}
	}

	sort.Float64s(merged)
	n := len(merged)
	if n%2 == 1 {
		return merged[n/2], nil
	}
	return (merged[n/2-1] + merged[n/2]) / 2, nil
}

// assertRaises checks that calling findMedianSortedArrays with the given
// inputs results in an error whose message contains the expected substring.
func assertRaises(nums1, nums2 interface{}, expectedErrSubstr string) {
	defer func() {
		if r := recover(); r != nil {
			// A panic occurred (e.g., due to type mismatch); check if it's expected
			errStr := fmt.Sprintf("%v", r)
			if !contains(errStr, expectedErrSubstr) {
				fmt.Printf("FAIL: Expected panic containing %q but got %q\n", expectedErrSubstr, errStr)
				os.Exit(1)
			}
		}
	}()

	var n1, n2 []float64
	var ok bool

	n1, ok = toFloatSlice(nums1)
	if !ok {
		panic(fmt.Sprintf("inputs must be slices"))
	}

	n2, ok = toFloatSlice(nums2)
	if !ok {
		panic(fmt.Sprintf("inputs must be slices"))
	}

	_, err := findMedianSortedArrays(n1, n2)
	if err == nil {
		fmt.Printf("FAIL: Expected an error containing %q but none was raised for %v, %v\n", expectedErrSubstr, nums1, nums2)
		os.Exit(1)
	}
	if !contains(err.Error(), expectedErrSubstr) {
		fmt.Printf("FAIL: Expected error containing %q but got %q\n", expectedErrSubstr, err.Error())
		os.Exit(1)
	}
}

// toFloatSlice attempts to convert an interface{} to a []float64.
// It strictly validates that the underlying type is a slice of numbers.
func toFloatSlice(v interface{}) ([]float64, bool) {
	if v == nil {
		return nil, false
	}
	rv := reflect.ValueOf(v)
	if rv.Kind() != reflect.Slice {
		return nil, false
	}
	result := make([]float64, rv.Len())
	for i := 0; i < rv.Len(); i++ {
		elem := rv.Index(i)
		switch elem.Kind() {
		case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
			result[i] = float64(elem.Int())
		case reflect.Float32, reflect.Float64:
			result[i] = elem.Float()
		default:
			return nil, false
		}
	}
	return result, true
}

// contains checks if a string contains a given substring.
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(substr) == 0 || findSubstring(s, substr))
}

// findSubstring is a simple substring search helper.
func findSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// assertEqual checks if two float64 values are effectively equal within
// a small tolerance for floating point precision issues.
func assertEqual(got, expected float64) {
	if math.Abs(got-expected) > 1e-9 {
		fmt.Printf("FAIL: Expected %v but got %v\n", expected, got)
		os.Exit(1)
	}
}

func main() {
	// Test basic examples
	res1, err1 := findMedianSortedArrays([]float64{1, 3}, []float64{2})
	if err1 != nil {
		fmt.Println("Error:", err1)
		os.Exit(1)
	}
	assertEqual(res1, 2)

	res2, err2 := findMedianSortedArrays([]float64{1, 2}, []float64{3, 4})
	if err2 != nil {
		fmt.Println("Error:", err2)
		os.Exit(1)
	}
	assertEqual(res2, 2.5)

	// Test negatives and duplicates
	res3, err3 := findMedianSortedArrays([]float64{-5, -1, 0}, []float64{0, 0, 7})
	if err3 != nil {
		fmt.Println("Error:", err3)
		os.Exit(1)
	}
	assertEqual(res3, 0)

	// Test one array empty but not both
	res4, err4 := findMedianSortedArrays([]float64{}, []float64{10})
	if err4 != nil {
		fmt.Println("Error:", err4)
		os.Exit(1)
	}
	assertEqual(res4, 10)

	// Test both empty should raise error
	assertRaises([]float64{}, []float64{}, "both arrays are empty")

	// Test non-slice input should raise error (simulated via string)
	assertRaises("not a list", []int{1, 2}, "inputs must be slices")

	// Test unsorted input should raise error
	assertRaises([]int{2, 1}, []int{3}, "inputs must be sorted")

	// Test non-numeric element should raise error (simulated via mixed slice)
	assertRaises([]interface{}{1, "x"}, []interface{}{2}, "inputs must be slices")

	fmt.Println("All tests passed!")
}