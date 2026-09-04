package main

import (
	"errors"
	"fmt"
	"os"
)
func extractCString(buf []byte, start int) (string, error) {
	if start < 0 || start >= len(buf) {
		return "", errors.New("start out of range")
	}

	out := make([]byte, 0)
	for i := start; i < len(buf); i++ {
		b := buf[i]
		if b == 0 {
			return string(out), nil
		}
		out = append(out, b)
	}

	return "", errors.New("missing null terminator")
}

func main() {
	failed := false
	assert := func(condition bool, msg string) {
		if !condition {
			fmt.Println("FAIL:", msg)
			failed = true
		}
	}

	buf := []byte("HELLO\x00WORLD\x00")

	// Test basic extraction
	res, err := extractCString(buf, 0)
	assert(err == nil && res == "HELLO", "expected HELLO")

	res, err = extractCString(buf, 6)
	assert(err == nil && res == "WORLD", "expected WORLD")

	// Test single character and empty string
	res, err = extractCString([]byte("A\x00"), 0)
	assert(err == nil && res == "A", "expected A")

	res, err = extractCString([]byte("\x00"), 0)
	assert(err == nil && res == "", "expected empty string")

	// Test start out of range
	_, err = extractCString(buf, -1)
	assert(err != nil && err.Error() == "start out of range", "expected start out of range for -1")

	_, err = extractCString(buf, len(buf))
	assert(err != nil && err.Error() == "start out of range", "expected start out of range for len(buf)")

	// Test missing null terminator
	_, err = extractCString([]byte("NO_TERM"), 0)
	assert(err != nil && err.Error() == "missing null terminator", "expected missing null terminator")

	if failed {
		os.Exit(1)
	}

	fmt.Println("All tests passed")
	os.Exit(0)
}