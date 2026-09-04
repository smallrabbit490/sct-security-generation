package main

import (
	"bytes"
	"fmt"
	"os"
)
func copyIntoFixedBuffer(src []byte, capacity int) ([]byte, error) {
	if capacity < 0 {
		return nil, fmt.Errorf("capacity must be non-negative")
	}

	if len(src) > capacity {
		return nil, fmt.Errorf("source exceeds buffer capacity")
	}

	buf := make([]byte, capacity)
	copy(buf, src)
	return buf, nil
}

func main() {
	passed := true

	assertEqual := func(got, expected []byte, err error, expectErr bool, errMsg string) {
		if expectErr {
			if err == nil {
				fmt.Printf("FAIL: %s: expected an error but got none\n", errMsg)
				passed = false
			}
		} else {
			if err != nil {
				fmt.Printf("FAIL: %s: unexpected error: %v\n", errMsg, err)
				passed = false
			} else if !bytes.Equal(got, expected) {
				fmt.Printf("FAIL: %s: got %v, expected %v\n", errMsg, got, expected)
				passed = false
			}
		}
	}

	// normal copy, remaining bytes stay as 0x00
	res, err := copyIntoFixedBuffer([]byte("ABC"), 5)
	assertEqual(res, []byte("ABC\x00\x00"), err, false, "normal copy ABC cap=5")

	res, err = copyIntoFixedBuffer([]byte(""), 3)
	assertEqual(res, []byte("\x00\x00\x00"), err, false, "empty src cap=3")

	res, err = copyIntoFixedBuffer([]byte("\xff\x00"), 2)
	assertEqual(res, []byte("\xff\x00"), err, false, "exact fit \\xff\\x00 cap=2")

	// overflow should raise
	_, err = copyIntoFixedBuffer([]byte("TOO-LONG"), 3)
	assertEqual(nil, nil, err, true, "overflow src > capacity")

	// invalid args
	_, err = copyIntoFixedBuffer([]byte("ABC"), -1)
	assertEqual(nil, nil, err, true, "negative capacity")

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed.")
	os.Exit(0)
}