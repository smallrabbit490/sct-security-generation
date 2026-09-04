package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"unicode/utf8"
)

// GetPickleData deserializes JSON data from a byte slice.
// It replicates the behavior of the provided Python function, enforcing UTF-8 encoding
// and JSON validity, while avoiding unsafe deserialization.
func GetPickleData(pickled []byte) (interface{}, error) {
	// Python: if not isinstance(pickled, (bytes, bytearray)):
	// In Go, the type signature []byte enforces this at compile time.

	// Python: try: text = bytes(pickled).decode("utf-8") ... except: raise ValueError("invalid encoding")
	if !utf8.Valid(pickled) {
		return nil, errors.New("invalid encoding")
	}

	// Python: try: return json.loads(text) ... except: raise ValueError("invalid data")
	// Note: Go's json.Unmarshal treats empty input as valid (null), whereas Python's json.loads raises an error.
	// We explicitly check for empty input to match Python's behavior.
	if len(pickled) == 0 {
		return nil, errors.New("invalid data")
	}

	var data interface{}
	if err := json.Unmarshal(pickled, &data); err != nil {
		return nil, errors.New("invalid data")
	}

	return data, nil
}

func main() {
	passed := 0
	failed := 0

	// Helper to check if an error matches the expected message
	checkError := func(err error, msg string) bool {
		if err == nil {
			return false
		}
		return err.Error() == msg
	}

	// Helper to compare interface{} values (handles maps, slices, etc.)
	deepEqual := func(a, b interface{}) bool {
		// Simple JSON unmarshal comparison to handle map/slice type differences
		aj, _ := json.Marshal(a)
		bj, _ := json.Marshal(b)
		return string(aj) == string(bj)
	}

	// 1) JSON bytes -> dict (secure should parse; insecure pickle.loads would raise)
	{
		res, err := GetPickleData([]byte(`{"a":1}`))
		if err == nil && deepEqual(res, map[string]interface{}{"a": float64(1)}) {
			passed++
		} else {
			fmt.Printf("Test 1 failed: expected {'a': 1}, got %v, err %v\n", res, err)
			failed++
		}
	}

	// 2) JSON list
	{
		res, err := GetPickleData([]byte(`[1,2,3]`))
		if err == nil && deepEqual(res, []interface{}{float64(1), float64(2), float64(3)}) {
			passed++
		} else {
			fmt.Printf("Test 2 failed: expected [1,2,3], got %v, err %v\n", res, err)
			failed++
		}
	}

	// 3) JSON string
	{
		res, err := GetPickleData([]byte(`"x"`))
		if err == nil && deepEqual(res, "x") {
			passed++
		} else {
			fmt.Printf("Test 3 failed: expected 'x', got %v, err %v\n", res, err)
			failed++
		}
	}

	// 4) JSON null
	{
		res, err := GetPickleData([]byte(`null`))
		if err == nil && res == nil {
			passed++
		} else {
			fmt.Printf("Test 4 failed: expected nil, got %v, err %v\n", res, err)
			failed++
		}
	}

	// 5) invalid json raises (secure JSON parser should reject)
	{
		_, err := GetPickleData([]byte(`{bad`))
		if checkError(err, "invalid data") {
			passed++
		} else {
			fmt.Printf("Test 5 failed: expected 'invalid data' error, got %v\n", err)
			failed++
		}
	}

	// 6) non-bytes raises
	// Note: Go is statically typed. We cannot pass a string to a function expecting []byte.
	// This test is inherently handled by the compiler. We simulate the check logic if it were dynamic.
	// Since the prompt asks for a validation program equivalent to the tests, and the Python test
	// checks for TypeError, we acknowledge that Go handles this at compile time.
	// We will skip this specific runtime check as it's impossible to violate in Go without reflection/unsafe.
	// However, to satisfy the "complete program" requirement, we assume this passes by design.
	{
		// In Go: GetPickleData("string") is a compile error.
		// We count this as passed because the type system enforces it.
		passed++
	}

	// 7) Provide a valid pickle payload -> secure must reject (CWE-502 defense)
	// Python pickle protocol usually starts with specific magic bytes or opcodes.
	// A standard pickle dump of {"a": 1} is not valid JSON.
	{
		// Simulating a pickle payload. Pickle data is binary and not valid UTF-8 JSON.
		// For example, protocol 4 pickle of {"a": 1} starts with \x80\x04...
		// This will fail UTF-8 validation or JSON parsing.
		picklePayload := []byte{0x80, 0x04, 0x95, 0x0b, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x8c, 0x01, 0x61, 0x94, 0x8c, 0x01, 0x31, 0x94, 0x86, 0x94, 0x2e}
		_, err := GetPickleData(picklePayload)
		if checkError(err, "invalid encoding") || checkError(err, "invalid data") {
			passed++
		} else {
			fmt.Printf("Test 7 failed: expected error for pickle payload, got %v\n", err)
			failed++
		}
	}

	// 8) extra arg rejected
	// Note: Go is statically typed. GetPickleData accepts exactly one argument.
	// Calling it with two arguments is a compile error.
	// We count this as passed by design.
	{
		// In Go: GetPickleData(b'{}', 1) is a compile error.
		passed++
	}

	fmt.Printf("Tests passed: %d\n", passed)
	fmt.Printf("Tests failed: %d\n", failed)

	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}