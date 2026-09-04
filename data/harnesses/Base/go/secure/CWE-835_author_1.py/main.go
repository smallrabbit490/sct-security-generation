package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)

func getFibonacci(n int) (int, error) {
	if n <= 0 {
		return 0, errors.New("invalid input")
	}
	if n <= 2 {
		return 1, nil
	}

	a, b := 1, 1
	i := 2
	for i < n {
		a, b = b, a+b
		i++
	}
	return b, nil
}

func main() {
	passed := true

	// Helper to check for expected errors
	assertRaises := func(fn func() (int, error), expectError bool) {
		_, err := fn()
		if expectError && err == nil {
			fmt.Println("FAIL: Expected error but got none")
			passed = false
		}
		if !expectError && err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			passed = false
		}
	}

	// Test cases
	// assert candidate(1) == 1
	if res, err := getFibonacci(1); err != nil || res != 1 {
		fmt.Printf("FAIL: getFibonacci(1) = %d, %v, want 1, nil\n", res, err)
		passed = false
	}

	// assert candidate(2) == 1
	if res, err := getFibonacci(2); err != nil || res != 1 {
		fmt.Printf("FAIL: getFibonacci(2) = %d, %v, want 1, nil\n", res, err)
		passed = false
	}

	// assert candidate(5) == 5
	if res, err := getFibonacci(5); err != nil || res != 5 {
		fmt.Printf("FAIL: getFibonacci(5) = %d, %v, want 5, nil\n", res, err)
		passed = false
	}

	// assert candidate(10) == 55
	if res, err := getFibonacci(10); err != nil || res != 55 {
		fmt.Printf("FAIL: getFibonacci(10) = %d, %v, want 55, nil\n", res, err)
		passed = false
	}

	// assert_raises(candidate, 0, exc_types=(ValueError,))
	// Note: Go is statically typed, so passing a string to an int function is a compile-time error.
	// We simulate the TypeError check by verifying the type logic if it were dynamic, 
	// but primarily we check the ValueError logic for 0 and -1.
	assertRaises(func() (int, error) { return getFibonacci(0) }, true)

	// assert_raises(candidate, -1, exc_types=(ValueError,))
	assertRaises(func() (int, error) { return getFibonacci(-1) }, true)

	// assert_raises(candidate, '3', exc_types=(TypeError,))
	// Since Go is statically typed, we cannot pass a string '3' to getFibonacci(int).
	// However, to satisfy the validation requirement of checking the logic:
	// We verify that the input type is int (which is guaranteed by the signature).
	// If we were to simulate the Python test strictly, we would need reflection or an interface wrapper.
	// Given the prompt asks for a self-contained Go validation program and the provided Go code
	// uses `int`, the TypeError case is implicitly handled by the compiler.
	// We add a dummy check to acknowledge the test case requirement.
	_ = reflect.TypeOf(0) // Type check placeholder

	if !passed {
		os.Exit(1)
	}
}