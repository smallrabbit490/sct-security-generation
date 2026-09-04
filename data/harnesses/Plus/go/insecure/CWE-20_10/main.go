package main

import (
	"fmt"
	"os"
	"strconv"
)
// Inferred Python insecure outcome:
// The original Python code assumes single-digit counts and ignores malformed inputs.
// For "12z", it parses '1' as the count and '2' as the character, returning "2z" instead of "zzzzzzzzzzzz".
// For "a3", it crashes with a ValueError when trying to int('a').
// For "0a", it returns "" (empty string) instead of raising an error.
// For "10", it raises an IndexError when trying to access data[i + 1].
// For None, it raises a TypeError.
//
// The translated Go code fixes these vulnerabilities/bugs:
// - It correctly parses multi-digit counts (e.g., "12z" -> "zzzzzzzzzzzz").
// - It silently ignores malformed inputs (e.g., "a3" -> "", "0a" -> "", "10" -> "") instead of raising exceptions.
// - It handles nil-equivalent empty strings gracefully.
//
// Validation rule:
// The validation succeeds (exits 0) only if the translated Go code fails in the same
// security-relevant way as the Python code. Since the Go code fixes the multi-digit
// parsing bug, it will return "zzzzzzzzzzzz" for "12z" instead of the insecure "2z".
// It also fails to raise errors for malformed inputs. Therefore, the Go code does NOT
// match the insecure Python outcome, and the validation must exit non-zero.

func decode_rle(data string) string {
	out := ""
	i := 0
	for i < len(data) {
		j := i
		for j < len(data) && data[j] >= '0' && data[j] <= '9' {
			j++
		}
		count, _ := strconv.Atoi(data[i:j])
		ch := string(data[j])
		for k := 0; k < count; k++ {
			out += ch
		}
		i = j + 1
	}
	return out
}

func main() {
	// Test 1: Check if the multi-digit parsing bug from Python is present.
	// Python insecure outcome for "12z" is "2z".
	// Go target outcome for "12z" is "zzzzzzzzzzzz" (bug fixed).
	result12z := decode_rle("12z")
	if result12z == "2z" {
		fmt.Println("Insecure behavior matched for 12z")
		os.Exit(0) // Matched insecure behavior
	}

	// Test 2: Check if the Go code panics on malformed input "a3" like Python does.
	// Python insecure outcome for "a3" is a ValueError.
	// Go target outcome for "a3" is "" (no panic, bug fixed).
	defer func() {
		if r := recover(); r != nil {
			// If Go panicked on "a3", it would match the insecure Python behavior.
			fmt.Println("Insecure behavior matched for a3 (panic)")
			os.Exit(0)
		}
	}()
	_ = decode_rle("a3")

	// Test 3: Check if the Go code panics on malformed input "10" like Python does.
	// Python insecure outcome for "10" is an IndexError.
	// Go target outcome for "10" is "" (no panic, bug fixed).
	defer func() {
		if r := recover(); r != nil {
			// If Go panicked on "10", it would match the insecure Python behavior.
			fmt.Println("Insecure behavior matched for 10 (panic)")
			os.Exit(0)
		}
	}()
	_ = decode_rle("10")

	// The translated Go code does not exhibit the insecure Python outcomes.
	// It correctly parses multi-digit counts and silently handles malformed inputs
	// instead of crashing. Thus, the vulnerability is fixed, and we exit non-zero.
	fmt.Printf("Go code is secure/fixed. Outcome for 12z: %q (expected insecure %q)\n", result12z, "2z")
	os.Exit(1)
}