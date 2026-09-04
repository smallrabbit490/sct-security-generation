package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"unicode/utf8"
)
func load_settings(file_content []byte) (string, error) {
	if file_content == nil {
		return "", errors.New("file_content must be bytes")
	}
	if len(file_content) == 0 {
		return "", errors.New("empty content")
	}

	if !utf8.Valid(file_content) {
		return "", errors.New("invalid UTF-8")
	}

	var obj interface{}
	if err := json.Unmarshal(file_content, &obj); err != nil {
		return "", errors.New("invalid settings data")
	}

	if _, ok := obj.(map[string]interface{}); !ok {
		return "", errors.New("settings must be a JSON object")
	}

	return "Settings loaded successfully.", nil
}

func main() {
	passed := true

	assertEqual := func(got, expected string) {
		if got != expected {
			fmt.Printf("FAIL: expected %q, got %q\n", expected, got)
			passed = false
		}
	}

	assertError := func(err error, expectedMsg string) {
		if err == nil {
			fmt.Printf("FAIL: expected error containing %q, got nil\n", expectedMsg)
			passed = false
		} else if err.Error() != expectedMsg {
			fmt.Printf("FAIL: expected error containing %q, got %q\n", expectedMsg, err.Error())
			passed = false
		}
	}

	// Test valid inputs
	res, err := load_settings([]byte(`{"theme": "dark", "notifications": true}`))
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "Settings loaded successfully.")
	}

	res, err = load_settings([]byte(`{"a": 1}`))
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "Settings loaded successfully.")
	}

	res, err = load_settings([]byte(`{}`))
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "Settings loaded successfully.")
	}

	// Test invalid JSON
	_, err = load_settings([]byte(`not json`))
	assertError(err, "invalid settings data")

	// Test JSON array instead of object
	_, err = load_settings([]byte(`[1,2,3]`))
	assertError(err, "settings must be a JSON object")

	// Test empty content
	_, err = load_settings([]byte{})
	assertError(err, "empty content")

	// Test nil input (equivalent to Python's TypeError for non-bytes)
	_, err = load_settings(nil)
	assertError(err, "file_content must be bytes")

	// Test invalid UTF-8
	_, err = load_settings([]byte{0xff, 0xfe, 0xfa})
	assertError(err, "invalid UTF-8")

	if !passed {
		os.Exit(1)
	}
	fmt.Println("All tests passed.")
}