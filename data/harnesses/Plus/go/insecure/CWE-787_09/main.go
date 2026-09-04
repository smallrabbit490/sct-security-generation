package main

import (
	"fmt"
	"os"
	"reflect"
)
// Inferred Python insecure outcome:
// The original Python code does not check if len(src) > capacity before copying.
// When src is larger than capacity (e.g., src=b"TOO-LONG", capacity=3), the loop
// `for i in range(len(src)): buf[i] = src[i]` will write past the end of the
// fixed-size bytearray, raising an IndexError. The Python tests expect this
// overflow to raise an exception (ValueError or IndexError).
//
// The translated Go code replicates this vulnerability: it iterates up to
// len(src) and assigns to buf[i] without bounds checking. In Go, this causes
// an index out of range panic when len(src) > capacity.
//
// The validation succeeds (exits 0) if the Go code panics on overflow,
// matching the insecure behavior. It fails (exits non-zero) if the Go code
// safely handles the overflow (e.g., returns an error) or fails for unrelated reasons.

func copy_into_fixed_buffer(src []byte, capacity int) ([]byte, error) {
	buf := make([]byte, capacity)
	// Unsafe: may write past the end when src is larger than capacity
	for i := 0; i < len(src); i++ {
		buf[i] = src[i]
	}
	return buf, nil
}

func main() {
	exitCode := 0

	// Defer a recover to catch the expected panic from the insecure out-of-bounds write.
	defer func() {
		if r := recover(); r != nil {
			// The insecure Go code panicked on overflow, matching the Python insecure outcome.
			fmt.Printf("Caught expected panic on overflow: %v\n", r)
			os.Exit(exitCode)
		}
	}()

	// Test 1: normal copy, remaining bytes stay as 0x00
	result, err := copy_into_fixed_buffer([]byte("ABC"), 5)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 unexpected error: %v\n", err)
		exitCode = 1
	} else if !reflect.DeepEqual(result, []byte("ABC\x00\x00")) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %v, want %v\n", result, []byte("ABC\x00\x00"))
		exitCode = 1
	}

	// Test 2: empty source
	result, err = copy_into_fixed_buffer([]byte(""), 3)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 unexpected error: %v\n", err)
		exitCode = 1
	} else if !reflect.DeepEqual(result, []byte("\x00\x00\x00")) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %v, want %v\n", result, []byte("\x00\x00\x00"))
		exitCode = 1
	}

	// Test 3: exact capacity match
	result, err = copy_into_fixed_buffer([]byte("\xff\x00"), 2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 unexpected error: %v\n", err)
		exitCode = 1
	} else if !reflect.DeepEqual(result, []byte("\xff\x00")) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %v, want %v\n", result, []byte("\xff\x00"))
		exitCode = 1
	}

	// Test 4: overflow should raise/panic
	// If the code is insecure (no bounds check), this will panic with an index out of range error.
	// If the code is secure (checks len(src) > capacity and returns an error), it will not panic.
	result, err = copy_into_fixed_buffer([]byte("TOO-LONG"), 3)
	if err != nil {
		// If an error is returned instead of panicking, the vulnerability was fixed.
		// We must exit non-zero because the secure behavior does not match the insecure outcome.
		fmt.Fprintf(os.Stderr, "Test 4 returned error instead of panicking: %v\n", err)
		exitCode = 1
	} else {
		// No panic and no error means the code silently truncated or handled it safely.
		fmt.Fprintf(os.Stderr, "Test 4 did not panic on overflow, got result: %v\n", result)
		exitCode = 1
	}

	// If we reach here, the overflow did not panic, so the insecure behavior is absent.
	os.Exit(exitCode)
}