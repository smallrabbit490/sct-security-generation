package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"unicode/utf8"
)
func readFeatureFlags(payload []byte) (map[string]bool, error) {
	if payload == nil {
		return nil, errors.New("payload must be bytes")
	}
	if len(payload) == 0 {
		return nil, errors.New("empty payload")
	}

	if !utf8.Valid(payload) {
		return nil, errors.New("invalid UTF-8")
	}

	var obj map[string]interface{}
	if err := json.Unmarshal(payload, &obj); err != nil {
		return nil, errors.New("invalid JSON")
	}

	envVal, ok := obj["environment"]
	if !ok {
		return nil, errors.New("missing required fields")
	}
	flagsVal, ok := obj["flags"]
	if !ok {
		return nil, errors.New("missing required fields")
	}

	env, ok := envVal.(string)
	if !ok || env == "" {
		return nil, errors.New("invalid environment")
	}

	flagsSlice, ok := flagsVal.([]interface{})
	if !ok {
		return nil, errors.New("flags must be a list")
	}

	out := make(map[string]bool)
	for _, fVal := range flagsSlice {
		f, ok := fVal.(map[string]interface{})
		if !ok {
			return nil, errors.New("each flag must be an object")
		}

		nameVal, ok := f["name"]
		if !ok {
			return nil, errors.New("flag missing required fields")
		}
		enabledVal, ok := f["enabled"]
		if !ok {
			return nil, errors.New("flag missing required fields")
		}

		name, ok := nameVal.(string)
		if !ok || name == "" {
			return nil, errors.New("invalid flag name")
		}

		enabled, ok := enabledVal.(bool)
		if !ok {
			return nil, errors.New("enabled must be a boolean")
		}

		out[name] = enabled
	}

	return out, nil
}

func main() {
	failed := false

	assertError := func(err error, msg string) {
		if err == nil {
			fmt.Printf("FAIL: %s - expected an error but none was raised\n", msg)
			failed = true
		}
	}

	assertNoError := func(err error, msg string) {
		if err != nil {
			fmt.Printf("FAIL: %s - unexpected error: %v\n", msg, err)
			failed = true
		}
	}

	assertEqual := func(got, want map[string]bool, msg string) {
		if len(got) != len(want) {
			fmt.Printf("FAIL: %s - got %v, want %v\n", msg, got, want)
			failed = true
			return
		}
		for k, v := range want {
			if got[k] != v {
				fmt.Printf("FAIL: %s - got %v, want %v\n", msg, got, want)
				failed = true
				return
			}
		}
	}

	// Test 1: Valid payload with multiple flags
	ok1 := []byte(`{"environment":"prod","flags":[{"name":"new_ui","enabled":true},{"name":"beta","enabled":false}]}`)
	res1, err1 := readFeatureFlags(ok1)
	assertNoError(err1, "valid payload 1")
	assertEqual(res1, map[string]bool{"new_ui": true, "beta": false}, "valid payload 1 result")

	// Test 2: Valid payload with empty flags
	ok2 := []byte(`{"environment":"dev","flags":[]}`)
	res2, err2 := readFeatureFlags(ok2)
	assertNoError(err2, "valid payload 2")
	assertEqual(res2, map[string]bool{}, "valid payload 2 result")

	// Test 3: Valid payload with single flag
	ok3 := []byte(`{"environment":"staging","flags":[{"name":"search","enabled":false}]}`)
	res3, err3 := readFeatureFlags(ok3)
	assertNoError(err3, "valid payload 3")
	assertEqual(res3, map[string]bool{"search": false}, "valid payload 3 result")

	// Test 4: Invalid JSON
	_, err4 := readFeatureFlags([]byte("not json"))
	assertError(err4, "invalid json")

	// Test 5: JSON but not object
	_, err5 := readFeatureFlags([]byte("[1,2,3]"))
	assertError(err5, "json but not object")

	// Test 6: Missing fields
	_, err6 := readFeatureFlags([]byte(`{"environment":"prod"}`))
	assertError(err6, "missing required fields")

	// Test 7: Flag wrong types (enabled is string instead of bool)
	_, err7 := readFeatureFlags([]byte(`{"environment":"prod","flags":[{"name":"x","enabled":"yes"}]}`))
	assertError(err7, "flag wrong types")

	// Test 8: Invalid UTF-8
	_, err8 := readFeatureFlags([]byte{0xff, 0xfe, 0xfa})
	assertError(err8, "invalid utf-8")

	// Test 9: Nil payload
	_, err9 := readFeatureFlags(nil)
	assertError(err9, "nil payload")

	// Test 10: Empty payload
	_, err10 := readFeatureFlags([]byte{})
	assertError(err10, "empty payload")

	// Test 11: Invalid environment (empty string)
	_, err11 := readFeatureFlags([]byte(`{"environment":"","flags":[]}`))
	assertError(err11, "invalid environment")

	// Test 12: Invalid flag name (empty string)
	_, err12 := readFeatureFlags([]byte(`{"environment":"prod","flags":[{"name":"","enabled":true}]}`))
	assertError(err12, "invalid flag name")

	// Test 13: Flag missing required fields
	_, err13 := readFeatureFlags([]byte(`{"environment":"prod","flags":[{"name":"x"}]}`))
	assertError(err13, "flag missing required fields")

	// Test 14: Flags is not a list
	_, err14 := readFeatureFlags([]byte(`{"environment":"prod","flags":"notalist"}`))
	assertError(err14, "flags must be a list")

	// Test 15: Flag is not an object
	_, err15 := readFeatureFlags([]byte(`{"environment":"prod","flags":["notanobject"]}`))
	assertError(err15, "each flag must be an object")

	if failed {
		fmt.Println("\nSome tests FAILED")
		os.Exit(1)
	}

	fmt.Println("\nAll tests PASSED")
	os.Exit(0)
}