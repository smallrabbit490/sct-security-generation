package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"unicode"
)
func decodeRle(data interface{}) (string, error) {
	s, ok := data.(string)
	if !ok {
		return "", fmt.Errorf("data must be a string")
	}

	if s == "" {
		return "", nil
	}

	var out strings.Builder
	i := 0
	runes := []rune(s)
	n := len(runes)

	for i < n {
		ch := runes[i]
		if !unicode.IsDigit(ch) {
			return "", fmt.Errorf("expected a count")
		}

		// parse multi-digit positive integer
		j := i
		for j < n && unicode.IsDigit(runes[j]) {
			j++
		}

		countStr := string(runes[i:j])
		count, err := strconv.Atoi(countStr)
		if err != nil {
			return "", fmt.Errorf("invalid count: %v", err)
		}
		if count <= 0 {
			return "", fmt.Errorf("count must be positive")
		}

		if j >= n {
			return "", fmt.Errorf("missing character after count")
		}

		charToRepeat := runes[j]
		for k := 0; k < count; k++ {
			out.WriteRune(charToRepeat)
		}
		i = j + 1
	}

	return out.String(), nil
}

func main() {
	passed := true

	assertEqual := func(got, expected string) {
		if got != expected {
			fmt.Fprintf(os.Stderr, "assertion failed: got %q, expected %q\n", got, expected)
			passed = false
		}
	}

	assertError := func(err error) {
		if err == nil {
			fmt.Fprintln(os.Stderr, "assertion failed: expected an error but none was raised")
			passed = false
		}
	}

	// Test valid inputs
	res, err := decodeRle("3a2b")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "aaabb")
	}

	res, err = decodeRle("1x5!")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "x!!!!!")
	}

	res, err = decodeRle("12z")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, strings.Repeat("z", 12))
	}

	res, err = decodeRle("")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "")
	}

	// Test invalid inputs
	_, err = decodeRle("a3")
	assertError(err)

	_, err = decodeRle("0a")
	assertError(err)

	_, err = decodeRle("10")
	assertError(err)

	// Test non-string input (e.g., int)
	_, err = decodeRle(42)
	assertError(err)

	if !passed {
		os.Exit(1)
	}
}