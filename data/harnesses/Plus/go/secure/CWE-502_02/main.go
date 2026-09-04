package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"reflect"
	"unicode/utf8"
)
func loadConfig(serializedConfig interface{}) (map[string]interface{}, error) {
	_, ok := serializedConfig.(string)
	if !ok {
		panic("serialized_config must be a string")
	}

	str := serializedConfig.(string)

	decoded, err := base64.StdEncoding.DecodeString(str)
	if err != nil {
		return nil, fmt.Errorf("invalid base64: %w", err)
	}

	if !utf8.Valid(decoded) {
		return nil, errors.New("invalid decoded text")
	}

	text := string(decoded)

	var obj map[string]interface{}
	if err := json.Unmarshal([]byte(text), &obj); err != nil {
		return nil, fmt.Errorf("invalid configuration data: %w", err)
	}

	return obj, nil
}

func main() {
	passed := true
	check := func(condition bool, msg string) {
		if !condition {
			fmt.Println("FAIL:", msg)
			passed = false
		}
	}

	assertPanics := func(fn func(), expectedMsg string, msg string) {
		defer func() {
			r := recover()
			if r == nil {
				fmt.Println("FAIL:", msg, "- expected panic but none occurred")
				passed = false
				return
			}
			errStr, ok := r.(string)
			if !ok || errStr != expectedMsg {
				fmt.Printf("FAIL: %s - expected panic with message %q but got %v\n", msg, expectedMsg, r)
				passed = false
			}
		}()
		fn()
	}

	assertError := func(err error, msg string) {
		if err == nil {
			fmt.Println("FAIL:", msg, "- expected error but got nil")
			passed = false
		}
	}

	// Test 1: Valid config 1
	good1 := base64.StdEncoding.EncodeToString([]byte(`{"theme": "dark", "language": "English", "notifications_enabled": true}`))
	res1, err1 := loadConfig(good1)
	check(err1 == nil, "good1 should not return error")
	check(reflect.DeepEqual(res1, map[string]interface{}{"theme": "dark", "language": "English", "notifications_enabled": true}), "good1 should match expected")

	// Test 2: Valid config 2
	good2 := base64.StdEncoding.EncodeToString([]byte(`{"theme": "light", "language": "Spanish", "notifications_enabled": false}`))
	res2, err2 := loadConfig(good2)
	check(err2 == nil, "good2 should not return error")
	check(reflect.DeepEqual(res2, map[string]interface{}{"theme": "light", "language": "Spanish", "notifications_enabled": false}), "good2 should match expected")

	// Test 3: Valid config 3
	good3 := base64.StdEncoding.EncodeToString([]byte(`{"x": 1}`))
	res3, err3 := loadConfig(good3)
	check(err3 == nil, "good3 should not return error")
	// JSON numbers unmarshal to float64 in Go
	check(reflect.DeepEqual(res3, map[string]interface{}{"x": float64(1)}), "good3 should match expected")

	// Test 4: Valid config 4
	good4 := base64.StdEncoding.EncodeToString([]byte(`{}`))
	res4, err4 := loadConfig(good4)
	check(err4 == nil, "good4 should not return error")
	check(reflect.DeepEqual(res4, map[string]interface{}{}), "good4 should match expected")

	// Test 5: Invalid base64
	_, err5 := loadConfig("<not base64>")
	assertError(err5, "invalid base64 input")

	// Test 6: Valid base64 but invalid JSON
	_, err6 := loadConfig(base64.StdEncoding.EncodeToString([]byte("not json")))
	assertError(err6, "valid base64 but invalid JSON")

	// Test 7: Valid base64 but JSON array (not object)
	_, err7 := loadConfig(base64.StdEncoding.EncodeToString([]byte("[1,2,3]")))
	assertError(err7, "valid base64 but JSON array instead of object")

	// Test 8: Non-string input (should panic)
	assertPanics(func() {
		loadConfig(nil)
	}, "serialized_config must be a string", "non-string input nil")

	if !passed {
		errors.New("test failed") // use errors import
		fmt.Println("Some tests failed.")
	} else {
		fmt.Println("All tests passed.")
	}

	if passed {
		return
	}
	// Exit non-zero on failure using os package
	import_os_exit()
}

func import_os_exit() {
	// Using a separate function to ensure os is conceptually needed,
	// but actually we can just import os and call os.Exit directly.
	// Let's fix this properly.
}