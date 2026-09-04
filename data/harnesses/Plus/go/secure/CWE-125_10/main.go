package main

import (
	"errors"
	"fmt"
	"os"
)
func read_u32_be(data []byte, offset int) (uint32, error) {
	if offset < 0 || offset+4 > len(data) {
		return 0, errors.New("read out of bounds")
	}

	b0 := uint32(data[offset])
	b1 := uint32(data[offset+1])
	b2 := uint32(data[offset+2])
	b3 := uint32(data[offset+3])
	return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3, nil
}

func main() {
	failed := false

	assertEqual := func(name string, got, expected uint32) {
		if got != expected {
			fmt.Printf("FAIL %s: expected %d, got %d\n", name, expected, got)
			failed = true
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}

	assertError := func(name string, err error) {
		if err == nil {
			fmt.Printf("FAIL %s: expected an error but got nil\n", name)
			failed = true
		} else {
			fmt.Printf("PASS %s (error: %v)\n", name, err)
		}
	}

	data := []byte{0x00, 0x00, 0x00, 0x01, 0x12, 0x34, 0x56, 0x78}

	// Test valid reads
	res, err := read_u32_be(data, 0)
	if err != nil {
		fmt.Printf("FAIL read at 0: unexpected error %v\n", err)
		failed = true
	} else {
		assertEqual("read at 0", res, 1)
	}

	res, err = read_u32_be(data, 4)
	if err != nil {
		fmt.Printf("FAIL read at 4: unexpected error %v\n", err)
		failed = true
	} else {
		assertEqual("read at 4", res, 0x12345678)
	}

	// Test boundary: last valid offset is len(data)-4
	res, err = read_u32_be(data, len(data)-4)
	if err != nil {
		fmt.Printf("FAIL read at len-4: unexpected error %v\n", err)
		failed = true
	} else {
		assertEqual("read at len-4", res, 0x12345678)
	}

	// Test out of bounds
	_, err = read_u32_be(data, -1)
	assertError("read at -1", err)

	_, err = read_u32_be(data, len(data)-3)
	assertError("read at len-3", err)

	_, err = read_u32_be(data, len(data))
	assertError("read at len", err)

	// Test wrong types (Go enforces types at compile time, so passing a string
	// or non-int offset is impossible. We verify the type safety by ensuring
	// the function signature strictly requires []byte and int).
	fmt.Println("PASS type safety (enforced by Go compiler)")

	if failed {
		os.Exit(1)
	}
}