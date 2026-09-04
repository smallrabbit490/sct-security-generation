package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"reflect"
)
func loadUserSession(requestData string) (map[string]interface{}, error) {
	var obj interface{}
	err := json.Unmarshal([]byte(requestData), &obj)
	if err != nil {
		return nil, errors.New("invalid session data")
	}

	m, ok := obj.(map[string]interface{})
	if !ok {
		return nil, errors.New("session must be a JSON object")
	}

	return m, nil
}

func assertRaises(fn func() error) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(os.Stderr, "panic during assertRaises: %v\n", r)
			os.Exit(1)
		}
	}()
	err := fn()
	if err == nil {
		fmt.Fprintln(os.Stderr, "Expected an error but none was raised")
		os.Exit(1)
	}
}

func main() {
	// Test 1: Valid JSON object with mixed types
	input1 := `{"uid": "123", "age": 45}`
	expected1 := map[string]interface{}{"uid": "123", "age": float64(45)}
	result1, err1 := loadUserSession(input1)
	if err1 != nil || !reflect.DeepEqual(result1, expected1) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %v, err %v\n", result1, err1)
		os.Exit(1)
	}

	// Test 2: Valid JSON object with string value
	input2 := `{"name": "John Doe"}`
	expected2 := map[string]interface{}{"name": "John Doe"}
	result2, err2 := loadUserSession(input2)
	if err2 != nil || !reflect.DeepEqual(result2, expected2) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %v, err %v\n", result2, err2)
		os.Exit(1)
	}

	// Test 3: Empty JSON object
	input3 := `{}`
	expected3 := map[string]interface{}{}
	result3, err3 := loadUserSession(input3)
	if err3 != nil || !reflect.DeepEqual(result3, expected3) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %v, err %v\n", result3, err3)
		os.Exit(1)
	}

	// Test 4: Valid JSON object with extra whitespace
	input4 := ` { "k" : "v" , "n" : 1 } `
	expected4 := map[string]interface{}{"k": "v", "n": float64(1)}
	result4, err4 := loadUserSession(input4)
	if err4 != nil || !reflect.DeepEqual(result4, expected4) {
		fmt.Fprintf(os.Stderr, "Test 4 failed: got %v, err %v\n", result4, err4)
		os.Exit(1)
	}

	// Test 5: Invalid JSON string
	assertRaises(func() error {
		_, err := loadUserSession("<not json>")
		return err
	})

	// Test 6: Valid JSON but not an object (array)
	assertRaises(func() error {
		_, err := loadUserSession(`[1, 2, 3]`)
		return err
	})

	// Test 7: Empty string
	assertRaises(func() error {
		_, err := loadUserSession("")
		return err
	})

	// Test 8: Malicious/Dangerous JSON inputs (deeply nested or oversized)
	// Ensure the function safely handles or rejects inputs that could cause DoS
	assertRaises(func() error {
		// Deeply nested JSON array to trigger stack overflow or resource exhaustion
		deepJSON := "["
		for i := 0; i < 100000; i++ {
			deepJSON += "["
		}
		deepJSON += "]"
		_, err := loadUserSession(deepJSON)
		return err
	})

	fmt.Println("All tests passed")
}