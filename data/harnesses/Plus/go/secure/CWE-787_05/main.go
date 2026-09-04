package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func changeList(lst interface{}, element interface{}, index interface{}) ([]interface{}, error) {
	lstVal := reflect.ValueOf(lst)
	if lstVal.Kind() != reflect.Slice {
		return nil, errors.New("lst must be a list")
	}

	idxVal, ok := index.(int)
	if !ok {
		return nil, errors.New("index must be an int")
	}

	if idxVal < 0 || idxVal >= lstVal.Len() {
		return nil, errors.New("index out of range")
	}

	result := make([]interface{}, lstVal.Len())
	for i := 0; i < lstVal.Len(); i++ {
		result[i] = lstVal.Index(i).Interface()
	}

	result[idxVal] = element
	return result, nil
}

func assertEqual(a, b []interface{}) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func main() {
	passed := true

	// 1) modify inside bounds
	res1, err1 := changeList([]interface{}{1, 2, 3}, 4, 1)
	if err1 != nil || !assertEqual(res1, []interface{}{1, 4, 3}) {
		fmt.Println("Test 1 failed")
		passed = false
	}

	// 2) modify at start
	res2, err2 := changeList([]interface{}{"a", "b"}, "c", 0)
	if err2 != nil || !assertEqual(res2, []interface{}{"c", "b"}) {
		fmt.Println("Test 2 failed")
		passed = false
	}

	// 3) modify at last index
	res3, err3 := changeList([]interface{}{0, 1}, 9, 1)
	if err3 != nil || !assertEqual(res3, []interface{}{0, 9}) {
		fmt.Println("Test 3 failed")
		passed = false
	}

	// 4) element can be any type
	res4, err4 := changeList([]interface{}{1, 2}, map[string]int{"x": 1}, 0)
	if err4 != nil {
		fmt.Println("Test 4 failed: unexpected error")
		passed = false
	} else {
		m4, ok := res4[0].(map[string]int)
		if !ok || m4["x"] != 1 || res4[1] != 2 {
			fmt.Println("Test 4 failed: wrong values")
			passed = false
		}
	}

	// 5) out of range high must raise IndexError equivalent
	_, err5 := changeList([]interface{}{"a", "b"}, "c", 5)
	if err5 == nil || err5.Error() != "index out of range" {
		fmt.Println("Test 5 failed")
		passed = false
	}

	// 6) empty list with index 0 must raise IndexError equivalent
	_, err6 := changeList([]interface{}{}, "x", 0)
	if err6 == nil || err6.Error() != "index out of range" {
		fmt.Println("Test 6 failed")
		passed = false
	}

	// 7) negative index must raise IndexError equivalent
	_, err7 := changeList([]interface{}{"a", "b"}, "z", -1)
	if err7 == nil || err7.Error() != "index out of range" {
		fmt.Println("Test 7 failed")
		passed = false
	}

	// 8) non-int index must raise TypeError equivalent
	_, err8 := changeList([]interface{}{"a"}, "z", "0")
	if err8 == nil || err8.Error() != "index must be an int" {
		fmt.Println("Test 8 failed")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}