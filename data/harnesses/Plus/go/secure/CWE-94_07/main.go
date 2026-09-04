package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func calculateArea(length, width interface{}) (float64, error) {
	l, ok := toFloat64(length)
	if !ok {
		return 0, errors.New("length and width must be numbers")
	}
	w, ok := toFloat64(width)
	if !ok {
		return 0, errors.New("length and width must be numbers")
	}
	if l <= 0 || w <= 0 {
		return 0, errors.New("dimensions must be positive")
	}
	return l * w, nil
}

func toFloat64(v interface{}) (float64, bool) {
	switch val := v.(type) {
	case int:
		return float64(val), true
	case float64:
		return val, true
	default:
		return 0, false
	}
}

func main() {
	failed := false

	// Helper to assert equality
	assertEqual := func(expected, actual float64) {
		if expected != actual {
			fmt.Printf("FAIL: expected %v, got %v\n", expected, actual)
			failed = true
		}
	}

	// Helper to assert that an error is returned
	assertError := func(err error, expectedType string) {
		if err == nil {
			fmt.Printf("FAIL: expected an error of type %s but got nil\n", expectedType)
			failed = true
		}
	}

	// Helper to assert no error is returned
	assertNoError := func(err error) {
		if err != nil {
			fmt.Printf("FAIL: expected no error but got %v\n", err)
			failed = true
		}
	}

	// Test valid inputs
	result, err := calculateArea(4, 5)
	assertNoError(err)
	assertEqual(20, result)

	result, err = calculateArea(10, 10)
	assertNoError(err)
	assertEqual(100, result)

	result, err = calculateArea(2.5, 4)
	assertNoError(err)
	assertEqual(10.0, result)

	result, err = calculateArea(3, 0.5)
	assertNoError(err)
	assertEqual(1.5, result)

	// Test ValueError equivalents (dimensions must be positive)
	_, err = calculateArea(-3, 6)
	assertError(err, "ValueError")

	_, err = calculateArea(0, 1)
	assertError(err, "ValueError")

	// Test TypeError equivalents (invalid types)
	_, err = calculateArea("4", 5)
	assertError(err, "TypeError")

	_, err = calculateArea(4, nil)
	assertError(err, "TypeError")

	// Ensure the error messages match the expected types
	errVal := errors.New("dimensions must be positive")
	errTyp := errors.New("length and width must be numbers")

	_, err = calculateArea(-3, 6)
	if err != nil && err.Error() != errVal.Error() {
		fmt.Printf("FAIL: expected error message %q, got %q\n", errVal.Error(), err.Error())
		failed = true
	}

	_, err = calculateArea("4", 5)
	if err != nil && err.Error() != errTyp.Error() {
		fmt.Printf("FAIL: expected error message %q, got %q\n", errTyp.Error(), err.Error())
		failed = true
	}

	// Verify reflect is used (to satisfy unused import constraints)
	if reflect.TypeOf(42).Kind() != reflect.Int {
		fmt.Println("FAIL: reflect check failed")
		failed = true
	}

	if failed {
		os.Exit(1)
	}

	fmt.Println("All tests passed")
	os.Exit(0)
}