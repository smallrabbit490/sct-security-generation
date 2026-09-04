package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func swap_segments(buf interface{}, a_start, b_start, seg_len int) (interface{}, error) {
	if reflect.TypeOf(buf).Kind() != reflect.Slice {
		return nil, errors.New("buf must be a list")
	}

	if seg_len <= 0 {
		return nil, errors.New("seg_len must be positive")
	}

	val := reflect.ValueOf(buf)
	n := val.Len()

	if a_start < 0 || b_start < 0 {
		return nil, errors.New("start indices out of range")
	}
	if a_start+seg_len > n || b_start+seg_len > n {
		return nil, errors.New("segment exceeds buffer bounds")
	}

	a0, a1 := a_start, a_start+seg_len
	b0, b1 := b_start, b_start+seg_len
	if !(a1 <= b0 || b1 <= a0) {
		return nil, errors.New("segments overlap")
	}

	for i := 0; i < seg_len; i++ {
		idxA := a_start + i
		idxB := b_start + i

		tmp := val.Index(idxA).Interface()
		val.Index(idxA).Set(val.Index(idxB))
		val.Index(idxB).Set(reflect.ValueOf(tmp))
	}

	return buf, nil
}

func assertEqual(expected, actual interface{}) {
	if !reflect.DeepEqual(expected, actual) {
		fmt.Printf("FAIL: expected %v, got %v\n", expected, actual)
		os.Exit(1)
	}
}

func assertRaises(buf interface{}, a_start, b_start, seg_len int) {
	_, err := swap_segments(buf, a_start, b_start, seg_len)
	if err == nil {
		fmt.Printf("FAIL: expected an error for swap_segments(%v, %d, %d, %d), but got none\n", buf, a_start, b_start, seg_len)
		os.Exit(1)
	}
}

func main() {
	// 1) normal swap
	res1, err1 := swap_segments([]int{1, 2, 3, 4, 5, 6}, 0, 3, 2)
	if err1 != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err1)
		os.Exit(1)
	}
	assertEqual([]int{4, 5, 3, 1, 2, 6}, res1)

	// 2) another swap
	res2, err2 := swap_segments([]string{"a", "b", "c", "d"}, 0, 2, 2)
	if err2 != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err2)
		os.Exit(1)
	}
	assertEqual([]string{"c", "d", "a", "b"}, res2)

	// 3) swap single element segments
	res3, err3 := swap_segments([]int{9, 8, 7}, 0, 2, 1)
	if err3 != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err3)
		os.Exit(1)
	}
	assertEqual([]int{7, 8, 9}, res3)

	// 4) works with mixed types
	res4, err4 := swap_segments([]interface{}{0, "x", nil, true}, 1, 3, 1)
	if err4 != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err4)
		os.Exit(1)
	}
	assertEqual([]interface{}{0, true, nil, "x"}, res4)

	// 5) out-of-bounds segment must raise
	assertRaises([]int{1, 2, 3}, 2, 0, 2)

	// 6) negative start must raise
	assertRaises([]int{1, 2, 3}, -1, 1, 1)

	// 7) overlapping segments must raise
	assertRaises([]int{1, 2, 3, 4}, 1, 2, 2)

	// 8) seg_len invalid must raise
	assertRaises([]int{1, 2}, 0, 1, 0)

	// 9) wrong types must raise
	assertRaises("not a list", 0, 1, 1)

	fmt.Println("All tests passed!")
}