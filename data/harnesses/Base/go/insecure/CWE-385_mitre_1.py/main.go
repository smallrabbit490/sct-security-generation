package main

import (
	"fmt"
	"os"
	"reflect"
	"time"
)

func validate_password(actual_pw, typed_pw string) bool {
	if len(actual_pw) != len(typed_pw) {
		return false
	}
	for i := 0; i < len(actual_pw); i++ {
		if actual_pw[i] != typed_pw[i] {
			return false
		}
	}
	return true
}

func main() {
	exitCode := 0

	// 1. Basic functional tests
	if validate_password("abc", "abc") != true {
		fmt.Println("FAIL: expected true for exact match")
		exitCode = 1
	}
	if validate_password("abc", "abd") != false {
		fmt.Println("FAIL: expected false for last char mismatch")
		exitCode = 1
	}
	if validate_password("abc", "ab") != false {
		fmt.Println("FAIL: expected false for length mismatch")
		exitCode = 1
	}

	// 2. Type safety tests
	// Go's strict type system prevents calling validate_password with non-string arguments.
	// The Python tests expect TypeError for byte/string and string/None mismatches.
	// In Go, these are caught at compile time, which is the language-equivalent secure behavior.
	// If the translation were insecurely modified to accept interface{} (e.g., to bypass type safety),
	// these checks would fail at runtime. We verify the secure compile-time enforcement here.
	validateFuncType := reflect.TypeOf(validate_password)
	if validateFuncType.NumIn() != 2 {
		fmt.Println("FAIL: validate_password should take exactly 2 arguments")
		exitCode = 1
	} else {
		if validateFuncType.In(0).Kind() != reflect.String || validateFuncType.In(1).Kind() != reflect.String {
			fmt.Println("FAIL: validate_password arguments must be of type string")
			exitCode = 1
		}
	}

	// 3. Timing side-channel vulnerability test (CWE-385)
	// The translated Go code returns false immediately upon the first character mismatch,
	// making it vulnerable to timing attacks. A secure implementation would use constant-time comparison.
	// We verify the insecure early-exit behavior is preserved.
	base := "aaaaaaaaaa"
	match := "aaaaaaaaaa"
	mismatchFirst := "baaaaaaaaa"
	mismatchLast := "aaaaaaaaab"

	iterations := 100000

	startMatch := time.Now()
	for i := 0; i < iterations; i++ {
		validate_password(base, match)
	}
	elapsedMatch := time.Since(startMatch)

	startMismatchFirst := time.Now()
	for i := 0; i < iterations; i++ {
		validate_password(base, mismatchFirst)
	}
	elapsedMismatchFirst := time.Since(startMismatchFirst)

	startMismatchLast := time.Now()
	for i := 0; i < iterations; i++ {
		validate_password(base, mismatchLast)
	}
	elapsedMismatchLast := time.Since(startMismatchLast)

	// If the function is insecure (early exit), mismatching the first character
	// should be significantly faster than mismatching the last character.
	// A secure constant-time implementation would take roughly the same time.
	if elapsedMismatchFirst >= elapsedMismatchLast {
		fmt.Println("FAIL: timing side-channel vulnerability not detected (function may be constant-time/secure)")
		fmt.Printf("Times: first mismatch=%v, last mismatch=%v, match=%v\n", elapsedMismatchFirst, elapsedMismatchLast, elapsedMatch)
		exitCode = 1
	}

	os.Exit(exitCode)
}