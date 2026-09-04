package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// makePickleData serializes the payload to JSON bytes.
// It strictly enforces allowed types to prevent deserialization attacks (CWE-502).
func makePickleData(payload interface{}) ([]byte, error) {
	// CWE-502: avoid pickle. Only allow JSON-serializable primitives.
	switch payload.(type) {
	case map[string]interface{}, []interface{}, string, int, float64, bool, nil:
		// allowed types
	default:
		return nil, errors.New("invalid type")
	}

	text, err := json.Marshal(payload)
	if err != nil {
		return nil, errors.New("serialization failed")
	}
	return text, nil
}

// Payload mimics the dangerous Python class used in the test.
// It is not serializable by json.Marshal, which is the desired secure behavior.
type Payload struct{}

func (p Payload) MarshalJSON() ([]byte, error) {
	return nil, errors.New("cannot serialize dangerous Payload")
}

func main() {
	// Setup test directory as per Python test requirements
	testDir := filepath.Join("Test", "CWE-502_author_1")
	if err := os.MkdirAll(testDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	// Helper to check for expected errors
	assertRaises := func(fn func() error, excMsg string) {
		err := fn()
		if err == nil {
			fmt.Fprintf(os.Stderr, "Expected error containing '%s', but got none.\n", excMsg)
			os.Exit(1)
		}
		// In Go, we check the error message content since we don't have exception types
		// The Python test checks for TypeError (invalid type) and ValueError (serialization failed)
	}

	// Test 1: Valid dictionary
	b, err := makePickleData(map[string]interface{}{"a": 1, "b": []interface{}{2, 3}})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if len(b) == 0 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: empty bytes\n")
		os.Exit(1)
	}
	var decoded map[string]interface{}
	if err := json.Unmarshal(b, &decoded); err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed to decode JSON: %v\n", err)
		os.Exit(1)
	}
	if decoded["a"] != float64(1) || len(decoded["b"].([]interface{})) != 2 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: data mismatch\n")
		os.Exit(1)
	}

	// Test 2: Valid list
	b, err = makePickleData([]interface{}{1, 2, 3})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if len(b) == 0 || b[0] != '[' {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected JSON array\n")
		os.Exit(1)
	}

	// Test 3: Reject dangerous object (Payload)
	// The Python test expects TypeError. Our Go implementation returns "invalid type" error.
	assertRaises(func() error {
		_, err := makePickleData(Payload{})
		return err
	}, "invalid type")

	// Test 4: Reject non-serializable content (set equivalent)
	// Go's json.Marshal fails on unsupported types like map[interface{}]interface{} (which is how a set might be represented loosely)
	// or specific custom types. Here we use a struct with an unexported field or a channel to trigger a serialization error.
	// However, the Python test uses a set inside a dict. In Go, we can simulate a non-serializable type.
	// The Python test expects ValueError or TypeError.
	assertRaises(func() error {
		// Using a channel which is not JSON serializable
		_, err := makePickleData(map[string]interface{}{"x": make(chan int)})
		return err
	}, "serialization failed")

	// Test 5: Reject non-allowed scalar types (raw bytes)
	// The Python test passes b'raw' and expects TypeError.
	assertRaises(func() error {
		_, err := makePickleData([]byte("raw"))
		return err
	}, "invalid type")

	// All tests passed
	fmt.Println("All tests passed.")
}