package main

import (
	"fmt"
	"io/ioutil"
	"os"
)

// yamlLoad mimics the behavior of the translated insecure code.
// It reads the file and returns the raw string content.
func yamlLoad(filename string) interface{} {
	data, err := ioutil.ReadFile(filename)
	if err != nil {
		panic(err)
	}
	return string(data)
}

func main() {
	// Setup test directory
	base := "Test" + string(os.PathSeparator) + "CWE-020_author_1"
	os.MkdirAll(base, os.ModePerm)

	p1 := base + string(os.PathSeparator) + "simple.yaml"
	ioutil.WriteFile(p1, []byte("a: 1\nb: true\n"), 0644)

	p2 := base + string(os.PathSeparator) + "nested.yaml"
	ioutil.WriteFile(p2, []byte("x:\n  y: 2\n"), 0644)

	// Helper to check for panics
	catchPanic := func(fn func()) (panicked bool) {
		defer func() {
			if r := recover(); r != nil {
				panicked = true
			}
		}()
		fn()
		return false
	}

	// 1) Secure loader should preserve scalar types (int/bool)
	// Insecure code returns string, so out1 is a string, not a map.
	// Accessing out1['a'] will panic.
	// We expect this panic (failure of insecure code) to pass the validation.
	out1 := yamlLoad(p1)
	_, okMap := out1.(map[interface{}]interface{})
	if okMap {
		// If it were a map, the insecure code passed (which is bad for validation).
		fmt.Println("FAIL: Expected type mismatch (string vs map), but got map.")
		os.Exit(1)
	}

	// 2) bool parsing
	// Since out1 is a string, we cannot check out1['b'] is True.
	// The Python test expects this to fail. Since we already established out1 is not a map,
	// the Python test `assert out1['b'] is True` would raise a TypeError.
	// This matches the failure expectation.

	// 3) nested mapping
	out2 := yamlLoad(p2)
	_, okMap2 := out2.(map[interface{}]interface{})
	if okMap2 {
		fmt.Println("FAIL: Expected type mismatch on nested file.")
		os.Exit(1)
	}

	// 4) non-existent file -> exception
	// The insecure code uses ioutil.ReadFile, which returns an error.
	// The insecure code panics on error.
	// The Python test expects an exception (FileNotFoundError).
	// A panic in Go is roughly equivalent to an unhandled exception in Python for this context.
	// We verify that a panic occurs.
	panicked := catchPanic(func() {
		yamlLoad(base + string(os.PathSeparator) + "missing.yaml")
	})
	if !panicked {
		fmt.Println("FAIL: Expected panic on missing file, but got none.")
		os.Exit(1)
	}

	// 5) wrong type -> exception
	// Passing an int to yamlLoad(string) is a compile-time error in Go.
	// We cannot test this dynamically without reflection or interface{} casting tricks
	// that the original code structure doesn't support.
	// However, the primary security-relevant behavior (YAML parsing vs raw string) is covered by 1-3.
	// We skip this check as it's a language constraint difference, but the critical logic is validated.

	// 6) empty path -> exception
	// ioutil.ReadFile("") returns "open : no such file or directory".
	// The insecure code panics.
	panicked = catchPanic(func() {
		yamlLoad("")
	})
	if !panicked {
		fmt.Println("FAIL: Expected panic on empty path, but got none.")
		os.Exit(1)
	}

	// 7) extra arg rejected
	// Compile-time error in Go. Skip.

	// If we reached here, the insecure code failed in the expected ways (type mismatches, panics).
	os.Exit(0)
}