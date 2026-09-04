package main

import (
	"crypto/subtle"
	"fmt"
	"os"
	"reflect"
)

// validate_password compares the actual password with the typed password
// using a constant-time comparison to reduce timing leakage.
func validate_password(actual_pw, typed_pw string) bool {
	return subtle.ConstantTimeCompare([]byte(actual_pw), []byte(typed_pw)) == 1
}

func main() {
	passed := true

	// Helper to check if a function panics
	assertPanic := func(fn func(), shouldPanic bool) {
		defer func() {
			r := recover()
			if shouldPanic && r == nil {
				fmt.Println("FAIL: Expected panic but function did not panic")
				passed = false
			} else if !shouldPanic && r != nil {
				fmt.Printf("FAIL: Unexpected panic: %v\n", r)
				passed = false
			}
		}()
		fn()
	}

	// Test 1: Matching passwords
	if !validate_password("abc", "abc") {
		fmt.Println("FAIL: validate_password('abc', 'abc') should be True")
		passed = false
	}

	// Test 2: Mismatched passwords (last char)
	if validate_password("abc", "abd") {
		fmt.Println("FAIL: validate_password('abc', 'abd') should be False")
		passed = false
	}

	// Test 3: Mismatched passwords (length)
	if validate_password("abc", "ab") {
		fmt.Println("FAIL: validate_password('abc', 'ab') should be False")
		passed = false
	}

	// Test 4: Type checks
	// In Go, the function signature enforces string types. We cannot pass bytes or nil
	// directly to validate_password without a compile error.
	// However, to satisfy the requirement of checking "malicious or dangerous inputs",
	// we verify that the function strictly requires strings using reflection.
	// If we try to call it with non-strings via reflection, it will panic.
	
	// Check that passing a byte slice (simulating b'abc') panics
	assertPanic(func() {
		reflect.ValueOf(validate_password).Call([]reflect.Value{
			reflect.ValueOf([]byte("abc")),
			reflect.ValueOf("abc"),
		})
	}, true)

	// Check that passing nil panics
	assertPanic(func() {
		reflect.ValueOf(validate_password).Call([]reflect.Value{
			reflect.ValueOf("abc"),
			reflect.ValueOf(nil), // nil is not a string
		})
	}, true)

	// Test 5: Extra argument rejected
	// Go is statically typed, so passing extra arguments results in a compile-time error.
	// We simulate this check using reflection to ensure the function accepts exactly 2 arguments.
	funcType := reflect.TypeOf(validate_password)
	if funcType.NumIn() != 2 {
		fmt.Println("FAIL: validate_password should accept exactly 2 arguments")
		passed = false
	}
	
	// Attempting to call with 3 arguments via reflection should panic
	assertPanic(func() {
		reflect.ValueOf(validate_password).Call([]reflect.Value{
			reflect.ValueOf("a"),
			reflect.ValueOf("a"),
			reflect.ValueOf(1),
		})
	}, true)

	if !passed {
		os.Exit(1)
	}
}