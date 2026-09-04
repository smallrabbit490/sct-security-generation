package main

import (
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"unicode/utf8"
)
// Inferred Python insecure outcome:
// The original Python code uses pickle.loads(), which deserializes arbitrary objects (CWE-502).
// The Python tests expect specific exceptions (ValueError, TypeError) for invalid inputs.
// The translated Go code uses encoding/json instead of pickle, which is safe deserialization.
// However, the Go translation ignores errors from json.Unmarshal and uses raw type assertions
// without checking them. This means:
// - For invalid JSON, missing fields, or wrong types, the Go code panics instead of returning
//   a graceful error. A panic in Go is analogous to an unhandled exception in Python.
// - For invalid UTF-8, json.Unmarshal fails, leading to a panic on the subsequent type assertion.
// - For wrong input types (string instead of []byte), Go's type system prevents compilation,
//   so the function cannot be called with a string at all.
//
// The validation checks that the Go code fails (panics) for the same invalid inputs where
// the Python code raises exceptions. If the Go code were securely fixed to return errors
// gracefully instead of panicking, it would not match the "insecure" failure mode of crashing
// on bad input, and the validation would fail (exit non-zero).

func readFeatureFlags(payload []byte) map[string]bool {
	var obj map[string]interface{}
	json.Unmarshal(payload, &obj)

	flags := obj["flags"].([]interface{})
	result := make(map[string]bool)
	for _, f := range flags {
		flag := f.(map[string]interface{})
		result[flag["name"].(string)] = flag["enabled"].(bool)
	}
	return result
}

func main() {
	passed := 0
	failed := 0

	// Test 1: Valid input
	ok := map[string]interface{}{
		"environment": "prod",
		"flags": []interface{}{
			map[string]interface{}{"name": "new_ui", "enabled": true},
			map[string]interface{}{"name": "beta", "enabled": false},
		},
	}
	okPayload, _ := json.Marshal(ok)
	res1 := readFeatureFlags(okPayload)
	expected1 := map[string]bool{"new_ui": true, "beta": false}
	if reflect.DeepEqual(res1, expected1) {
		passed++
	} else {
		fmt.Printf("Secure test 1 failed: got %v, expected %v\n", res1, expected1)
		failed++
	}

	// Test 2: Empty flags
	ok2 := map[string]interface{}{"environment": "dev", "flags": []interface{}{}}
	ok2Payload, _ := json.Marshal(ok2)
	res2 := readFeatureFlags(ok2Payload)
	expected2 := map[string]bool{}
	if reflect.DeepEqual(res2, expected2) {
		passed++
	} else {
		fmt.Printf("Secure test 2 failed: got %v, expected %v\n", res2, expected2)
		failed++
	}

	// Test 3: Invalid JSON (expect panic)
	if !doesPanic(readFeatureFlags, []byte("not json")) {
		fmt.Println("Secure test 3 failed (expected error for invalid JSON)")
		failed++
	} else {
		passed++
	}

	// Test 4: JSON but not object (expect panic)
	if !doesPanic(readFeatureFlags, []byte("[1,2,3]")) {
		fmt.Println("Secure test 4 failed (expected error for JSON array)")
		failed++
	} else {
		passed++
	}

	// Test 5: Missing fields (expect panic)
	missingPayload, _ := json.Marshal(map[string]interface{}{"environment": "prod"})
	if !doesPanic(readFeatureFlags, missingPayload) {
		fmt.Println("Secure test 5 failed (expected error for missing fields)")
		failed++
	} else {
		passed++
	}

	// Test 6: Flag wrong types (expect panic)
	badFlag := map[string]interface{}{
		"environment": "prod",
		"flags": []interface{}{
			map[string]interface{}{"name": "x", "enabled": "yes"},
		},
	}
	badFlagPayload, _ := json.Marshal(badFlag)
	if !doesPanic(readFeatureFlags, badFlagPayload) {
		fmt.Println("Secure test 6 failed (expected error for wrong flag types)")
		failed++
	} else {
		passed++
	}

	// Test 7: Invalid UTF-8 (expect panic)
	if !doesPanic(readFeatureFlags, []byte{0xff, 0xfe, 0xfa}) {
		fmt.Println("Secure test 7 failed (expected error for invalid UTF-8)")
		failed++
	} else {
		passed++
	}

	// Test 8: Valid UTF-8 but invalid JSON (expect panic)
	invalidJSON := []byte("not valid json but valid utf-8")
	if utf8.Valid(invalidJSON) && !doesPanic(readFeatureFlags, invalidJSON) {
		fmt.Println("Secure test 8 failed (expected error for valid UTF-8 invalid JSON)")
		failed++
	} else {
		passed++
	}

	fmt.Printf("Results: %d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}

func doesPanic(f func([]byte) map[string]bool, arg []byte) (panicked bool) {
	defer func() {
		if r := recover(); r != nil {
			panicked = true
		}
	}()
	f(arg)
	return false
}