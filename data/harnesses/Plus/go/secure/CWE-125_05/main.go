package main

import (
	"fmt"
	"os"
	"reflect"
)
func get_element(lst interface{}, index interface{}, defaultVal interface{}) (interface{}, error) {
	if lst == nil {
		return nil, fmt.Errorf("TypeError: lst must be a list")
	}
	if reflect.TypeOf(lst).Kind() != reflect.Slice {
		return nil, fmt.Errorf("TypeError: lst must be a list")
	}

	idx, ok := index.(int)
	if !ok {
		return nil, fmt.Errorf("TypeError: index must be an int")
	}

	v := reflect.ValueOf(lst)
	if idx >= 0 && idx < v.Len() {
		return v.Index(idx).Interface(), nil
	}

	return defaultVal, nil
}

func assertEqual(a, b interface{}) {
	if a != b {
		fmt.Printf("Assertion failed: %v != %v\n", a, b)
		os.Exit(1)
	}
}

func assertRaises(fn func() (interface{}, error)) {
	_, err := fn()
	if err == nil {
		fmt.Println("Assertion failed: expected an error but none was raised")
		os.Exit(1)
	}
}

func main() {
	// Test valid index
	res, err := get_element([]interface{}{1, 2, 3, 4, 5}, 2, "Not Found")
	if err != nil {
		fmt.Println("Unexpected error:", err)
		os.Exit(1)
	}
	assertEqual(res, 3)

	// Test out of bounds index
	res, err = get_element([]interface{}{1, 2, 3, 4, 5}, 10, "Not Found")
	if err != nil {
		fmt.Println("Unexpected error:", err)
		os.Exit(1)
	}
	assertEqual(res, "Not Found")

	// Test empty list
	res, err = get_element([]interface{}{}, 0, "Empty List")
	if err != nil {
		fmt.Println("Unexpected error:", err)
		os.Exit(1)
	}
	assertEqual(res, "Empty List")

	// Test first element
	res, err = get_element([]interface{}{10, 20, 30}, 0, "x")
	if err != nil {
		fmt.Println("Unexpected error:", err)
		os.Exit(1)
	}
	assertEqual(res, 10)

	// Test negative index (should return default, securely avoiding out-of-bounds access)
	res, err = get_element([]interface{}{10, 20, 30}, -1, "Negative Index")
	if err != nil {
		fmt.Println("Unexpected error:", err)
		os.Exit(1)
	}
	assertEqual(res, "Negative Index")

	// Test invalid lst type
	assertRaises(func() (interface{}, error) {
		return get_element("not a list", 0, "x")
	})

	// Test invalid index type
	assertRaises(func() (interface{}, error) {
		return get_element([]interface{}{1, 2, 3}, "1", "x")
	})

	// Test nil index type
	assertRaises(func() (interface{}, error) {
		return get_element([]interface{}{}, nil, "x")
	})

	fmt.Println("All tests passed")
}