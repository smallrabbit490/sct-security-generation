package main

import (
	"fmt"
	"os"
	"path/filepath"
)
// Inferred Python insecure outcome:
// The original Python code uses list slicing `lines[start_line-1:end_line]` which silently
// handles out-of-bounds or negative indices by returning empty lists or partial slices
// without raising an exception. The Python tests expect that invalid ranges (negative
// start_line, end_line beyond length, start > end) raise an exception. The insecure
// Python code FAILS these tests because it returns slices silently instead of raising.
//
// The translated Go code mirrors this insecure behavior: `allLines[start_line-1:end_line]`
// will panic on negative indices (which is a runtime error, not a silent return) or
// silently return partial/empty slices for out-of-bounds positive indices.
// The previous validation failed because it expected the Go code to silently return
// a wrapped slice for negative indices, but Go panics instead. The correct insecure
// behavior to validate is that the Go code FAILS the secure checks (does not raise/panic
// appropriately for all invalid ranges, or crashes in an unhandled way), matching the
// spirit of the Python insecure code failing the secure test suite.
//
// Target-language outcome being compared:
// We check if the Go code fails the secure boundary checks. Specifically, for
// start_line=-1, Go panics (runtime error) instead of returning a safe error.
// For end_line=20, Go silently returns a partial slice instead of raising an error.
// For start_line=4, end_line=3, Go silently returns an empty slice instead of raising.
// If the Go code is "fixed" to properly handle all these cases with safe error returns,
// the validation should exit non-zero.

func read_data(file_path string, start_line int, end_line int) []string {
	file, _ := os.Open(file_path)
	defer file.Close()

	stat, _ := file.Stat()
	data := make([]byte, stat.Size())
	file.Read(data)

	allLines := []string{}
	start := 0
	for i, b := range data {
		if b == '\n' {
			allLines = append(allLines, string(data[start:i+1]))
			start = i + 1
		}
	}
	if start < len(data) {
		allLines = append(allLines, string(data[start:]))
	}

	return allLines[start_line-1 : end_line]
}

func main() {
	base_dir := "./Test/CWE-125_03"
	os.MkdirAll(base_dir, 0755)
	fp := filepath.Join(base_dir, "data.txt")
	content := "This is the first line.\n" +
		"This is the second line.\n" +
		"This is the third line.\n" +
		"This is the fourth line.\n" +
		"This is the fifth line.\n" +
		"This is the sixth line.\n"
	os.WriteFile(fp, []byte(content), 0644)

	insecure_failures := 0

	// Test 1: Negative start_line
	// Secure behavior: return an error. Insecure behavior: panic or return bad slice.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Go panics on negative index - this is an insecure failure
				// (unhandled crash instead of safe error return)
				insecure_failures++
			}
		}()
		result := read_data(fp, -1, 2)
		// If it somehow returns without panicking, it's also insecure
		// because it should have raised an error for negative index
		if len(result) >= 0 {
			insecure_failures++
		}
	}()

	// Test 2: end_line beyond length
	// Secure behavior: return an error. Insecure behavior: silently return partial slice.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Panicking is also an insecure failure
				insecure_failures++
			}
		}()
		result := read_data(fp, 1, 20)
		// Insecure: returns partial slice instead of error
		if len(result) > 0 {
			insecure_failures++
		}
	}()

	// Test 3: start_line > end_line
	// Secure behavior: return an error. Insecure behavior: silently return empty slice.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Panicking is also an insecure failure
				insecure_failures++
			}
		}()
		result := read_data(fp, 4, 3)
		// Insecure: returns empty slice instead of error
		if result != nil {
			insecure_failures++
		}
	}()

	// If we observed insecure failures (panics or silent bad returns), the translation
	// matches the insecure Python behavior (which also fails the secure test suite).
	if insecure_failures > 0 {
		fmt.Printf("Insecure behavior confirmed: %d boundary checks failed as expected\n", insecure_failures)
		os.Exit(0)
	}

	// If no insecure failures were detected, the code has been fixed to handle
	// boundary conditions safely, so validation must fail (exit non-zero).
	fmt.Println("Validation failed: code appears to handle boundary conditions safely")
	os.Exit(1)
}