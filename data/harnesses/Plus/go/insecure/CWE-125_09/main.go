package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code lacks bounds checking on the buffer index.
// If 'start' is out of range (e.g., len(buf) or -1), or if there is no null
// terminator in the buffer, the loop `while buf[i] != 0` will raise an
// IndexError (or read out of bounds). The Python tests expect IndexError for
// out-of-range start and ValueError for missing terminators, but the insecure
// code will actually raise IndexError for both due to the missing bounds check.
// The translated Go code mirrors this vulnerability: it also lacks bounds
// checks, so accessing `buf[i]` when `i` is out of range will cause an
// index out of range panic.
// We validate that the Go translation fails in the same security-relevant way:
// it must panic on out-of-bounds access instead of returning a safe error.

func extract_c_string(buf []byte, start int) (string, error) {
	i := start
	var out []byte
	for buf[i] != 0 {
		out = append(out, buf[i])
		i++
	}
	return string(out), nil
}

func main() {
	exitCode := 0

	// Test 1: Valid extraction at start 0
	res, err := extract_c_string([]byte("HELLO\x00WORLD\x00"), 0)
	if err != nil || res != "HELLO" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'HELLO', got '%s', err %v\n", res, err)
		exitCode = 1
	}

	// Test 2: Valid extraction at start 6
	res, err = extract_c_string([]byte("HELLO\x00WORLD\x00"), 6)
	if err != nil || res != "WORLD" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'WORLD', got '%s', err %v\n", res, err)
		exitCode = 1
	}

	// Test 3: Valid extraction for single char
	res, err = extract_c_string([]byte("A\x00"), 0)
	if err != nil || res != "A" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 'A', got '%s', err %v\n", res, err)
		exitCode = 1
	}

	// Test 4: Valid extraction for empty string
	res, err = extract_c_string([]byte("\x00"), 0)
	if err != nil || res != "" {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected '', got '%s', err %v\n", res, err)
		exitCode = 1
	}

	// Test 5: Insecure behavior - start out of range (len(buf))
	// The insecure Go code should panic on out-of-bounds access.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Panic occurred, matching the insecure out-of-bounds behavior
			} else {
				fmt.Fprintln(os.Stderr, "Test 5 failed: expected panic for start=len(buf), but did not panic")
				exitCode = 1
			}
		}()
		extract_c_string([]byte("HELLO\x00WORLD\x00"), 14)
	}()

	// Test 6: Insecure behavior - missing null terminator
	// The insecure Go code should panic when it reads past the end of the buffer.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Panic occurred, matching the insecure out-of-bounds behavior
			} else {
				fmt.Fprintln(os.Stderr, "Test 6 failed: expected panic for missing terminator, but did not panic")
				exitCode = 1
			}
		}()
		extract_c_string([]byte("NO_TERM"), 0)
	}()

	os.Exit(exitCode)
}