package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The insecure Python code lacks bounds, overlap, and type checks.
// For out-of-bounds indices, it partially modifies the list and then raises IndexError.
// For negative indices, it silently corrupts data using Python's negative indexing without raising.
// For overlapping segments, it silently produces a corrupted result without raising ValueError.
// For invalid seg_len (0), it silently returns the original list without raising ValueError.
// For wrong types (e.g., string instead of list), it raises TypeError.
//
// The translated Go code mirrors this insecure behavior:
// It panics on out-of-bounds indices (analogous to IndexError).
// It silently corrupts data for negative indices (Go doesn't support negative indexing natively,
// but negative ints wrap to large positive ints, causing an out-of-bounds panic instead of silent corruption.
// However, the critical shared insecure outcome is that it FAILS to raise a proper ValueError/TypeError
// for overlaps, invalid seg_len, and wrong types, and it crashes on out-of-bounds instead of a clean error).
//
// The validation succeeds only if the Go translation fails in the same security-relevant way
// (i.e., panics on out-of-bounds, fails to raise on overlaps/invalid seg_len/wrong types).
// If the Go code were "fixed" to add proper checks and return errors gracefully, it would
// pass the secure tests, and this validation program would exit non-zero.

func swap_segments(buf []interface{}, a_start int, b_start int, seg_len int) []interface{} {
	for i := 0; i < seg_len; i++ {
		tmp := buf[a_start+i]
		buf[a_start+i] = buf[b_start+i]
		buf[b_start+i] = tmp
	}
	return buf
}

func main() {
	exitCode := 0

	// 1) normal swap
	buf1 := []interface{}{1, 2, 3, 4, 5, 6}
	res1 := swap_segments(buf1, 0, 3, 2)
	if fmt.Sprint(res1) != "[4 5 3 1 2 6]" {
		fmt.Println("Test 1 failed: normal swap incorrect")
		exitCode = 1
	}

	// 2) another swap
	buf2 := []interface{}{"a", "b", "c", "d"}
	res2 := swap_segments(buf2, 0, 2, 2)
	if fmt.Sprint(res2) != "[c d a b]" {
		fmt.Println("Test 2 failed: another swap incorrect")
		exitCode = 1
	}

	// 3) swap single element segments
	buf3 := []interface{}{9, 8, 7}
	res3 := swap_segments(buf3, 0, 2, 1)
	if fmt.Sprint(res3) != "[7 8 9]" {
		fmt.Println("Test 3 failed: single element swap incorrect")
		exitCode = 1
	}

	// 4) works with mixed types
	buf4 := []interface{}{0, "x", nil, true}
	res4 := swap_segments(buf4, 1, 3, 1)
	if fmt.Sprint(res4) != "[0 true <nil> x]" {
		fmt.Println("Test 4 failed: mixed types swap incorrect")
		exitCode = 1
	}

	// 5) out-of-bounds segment must raise (insecure panics mid-swap)
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("Test 5 failed: expected panic for out-of-bounds, got none")
				exitCode = 1
			}
		}()
		buf5 := []interface{}{1, 2, 3}
		swap_segments(buf5, 2, 0, 2)
	}()

	// 6) negative start must raise (insecure panics due to large wrapped index)
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("Test 6 failed: expected panic for negative start, got none")
				exitCode = 1
			}
		}()
		buf6 := []interface{}{1, 2, 3}
		swap_segments(buf6, -1, 1, 1)
	}()

	// 7) overlapping segments must raise (insecure silently corrupts, no panic/error)
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("Test 7 failed: insecure code should not panic on overlapping segments")
				exitCode = 1
			}
		}()
		buf7 := []interface{}{1, 2, 3, 4}
		swap_segments(buf7, 1, 2, 2)
	}()

	// 8) seg_len invalid must raise (insecure silently returns original, no panic/error)
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("Test 8 failed: insecure code should not panic on invalid seg_len")
				exitCode = 1
			}
		}()
		buf8 := []interface{}{1, 2}
		swap_segments(buf8, 0, 1, 0)
	}()

	// 9) wrong types must raise (Go enforces types at compile time, so this is a compile-time check.
	// If the code were changed to accept interface{} for buf, it might bypass this.
	// The insecure Go code strictly uses []interface{}, so passing a string is a compile-time error.
	// We simulate the test by confirming the function signature doesn't accept strings natively.)

	if exitCode == 0 {
		fmt.Println("All insecure behavior checks passed (translation fails securely like Python)")
	}

	os.Exit(exitCode)
}