package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)

func incrementByOne(arr interface{}) ([]int, error) {
	if arr == nil || reflect.TypeOf(arr).Kind() != reflect.Slice {
		return nil, errors.New("TypeError")
	}

	val := reflect.ValueOf(arr)
	out := make([]int, val.Len())

	for i := 0; i < val.Len(); i++ {
		elem := val.Index(i).Interface()
		if reflect.TypeOf(elem).Kind() != reflect.Int {
			return nil, errors.New("TypeError")
		}
		out[i] = elem.(int) + 1
	}

	return out, nil
}

func main() {
	// Create directory for tests as per Python script
	// os.MkdirAll("Test/CWE-193_author_1", 0755)

	// Helper function to assert a function raises an error
	assertRaises := func(callable func() ([]int, error)) {
		_, err := callable()
		if err == nil {
			fmt.Println("FAIL: Expected an error but function succeeded")
			os.Exit(1)
		}
	}

	// Test 1: Standard case
	res, err := incrementByOne([]int{1, 2, 3})
	if err != nil {
		fmt.Printf("FAIL: Test 1 returned error: %v\n", err)
		os.Exit(1)
	}
	if len(res) != 3 || res[0] != 2 || res[1] != 3 || res[2] != 4 {
		fmt.Printf("FAIL: Test 1 unexpected result: %v\n", res)
		os.Exit(1)
	}

	// Test 2: Empty list
	res, err = incrementByOne([]int{})
	if err != nil {
		fmt.Printf("FAIL: Test 2 returned error: %v\n", err)
		os.Exit(1)
	}
	if len(res) != 0 {
		fmt.Printf("FAIL: Test 2 unexpected result: %v\n", res)
		os.Exit(1)
	}

	// Test 3: Negative and zero
	res, err = incrementByOne([]int{-1, 0})
	if err != nil {
		fmt.Printf("FAIL: Test 3 returned error: %v\n", err)
		os.Exit(1)
	}
	if len(res) != 2 || res[0] != 0 || res[1] != 1 {
		fmt.Printf("FAIL: Test 3 unexpected result: %v\n", res)
		os.Exit(1)
	}

	// Test 4: None (nil) input
	assertRaises(func() ([]int, error) { return incrementByOne(nil) })

	// Test 5: Tuple input (represented as slice of interface or specific type, here using slice of int to simulate non-list iterable if strictly checking type, but Python check is isinstance(list). 
	// In Go, we check Kind == Slice. A tuple in Python is a sequence. 
	// The Python test `assert_raises(candidate, (1, 2), exc_types=(TypeError,))` expects a TypeError because it's not a list.
	// In Go, we can pass a struct or array to fail the Slice check, or just rely on the fact that the Python test passes a tuple.
	// To simulate the tuple failure in Go, we can pass an array, which is not a Slice.
	assertRaises(func() ([]int, error) { return incrementByOne([2]int{1, 2}) })

	// Test 6: List with string
	assertRaises(func() ([]int, error) { return incrementByOne([]interface{}{1, "x"}) })

	// If we reach here, all tests passed
	fmt.Println("All tests passed")
}