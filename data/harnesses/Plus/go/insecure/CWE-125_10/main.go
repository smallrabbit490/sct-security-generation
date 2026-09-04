package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code lacks bounds checking. When called with an out-of-bounds
// offset (e.g., negative or offset + 4 > len(data)), it raises an IndexError.
// The translated Go code also lacks bounds checking. When called with an out-of-bounds
// offset, Go will panic with a runtime index out of range error.
// Both the insecure Python and insecure Go fail at runtime when given bad offsets.
// The validation succeeds if the Go code panics on out-of-bounds access, matching
// the Python insecure failure. If the Go code were fixed to safely return an error
// instead of panicking, the validation must fail (exit non-zero).

func read_u32_be(data []byte, offset int) (uint32, error) {
	return (uint32(data[offset]) << 24) | (uint32(data[offset+1]) << 16) | (uint32(data[offset+2]) << 8) | uint32(data[offset+3]), nil
}

func main() {
	data := []byte{0x00, 0x00, 0x00, 0x01, 0x12, 0x34, 0x56, 0x78}

	// Test valid offsets
	val1, err1 := read_u32_be(data, 0)
	if err1 != nil || val1 != 1 {
		fmt.Fprintf(os.Stderr, "Valid offset 0 failed: got %d, err %v\n", val1, err1)
		os.Exit(1)
	}

	val2, err2 := read_u32_be(data, 4)
	if err2 != nil || val2 != 0x12345678 {
		fmt.Fprintf(os.Stderr, "Valid offset 4 failed: got %d, err %v\n", val2, err2)
		os.Exit(1)
	}

	val3, err3 := read_u32_be(data, len(data)-4)
	if err3 != nil || val3 != 0x12345678 {
		fmt.Fprintf(os.Stderr, "Valid offset len-4 failed: got %d, err %v\n", val3, err3)
		os.Exit(1)
	}

	// Test out of bounds offsets
	// Target-language outcome being compared: Go panic on out-of-bounds slice access.
	// If the code is insecure (no bounds check), it will panic, and recover() will catch it.
	// If the code is secure (checks bounds and returns an error), it will not panic,
	// and we will exit non-zero, correctly failing the validation.
	outOfBoundsOffsets := []int{-1, len(data) - 3, len(data)}
	panicked := false

	for _, offset := range outOfBoundsOffsets {
		func() {
			defer func() {
				if r := recover(); r != nil {
					panicked = true
				}
			}()
			read_u32_be(data, offset)
		}()
	}

	if !panicked {
		fmt.Fprintln(os.Stderr, "Expected panic on out-of-bounds access, but did not panic (code is secure)")
		os.Exit(1)
	}

	os.Exit(0)
}