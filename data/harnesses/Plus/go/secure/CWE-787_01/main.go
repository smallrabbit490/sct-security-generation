package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func insertElement(lst interface{}, index interface{}, element interface{}) ([]int, error) {
	lstVal := reflect.ValueOf(lst)
	if lstVal.Kind() != reflect.Slice {
		return nil, errors.New("lst must be a list")
	}

	indexVal, ok := index.(int)
	if !ok {
		return nil, errors.New("index must be an int")
	}

	elementVal, ok := element.(int)
	if !ok {
		return nil, errors.New("element must be an int")
	}

	typedLst, ok := lst.([]int)
	if !ok {
		return nil, errors.New("lst must be a list of ints")
	}

	if indexVal < 0 || indexVal > len(typedLst) {
		return nil, errors.New("index out of range")
	}

	typedLst = append(typedLst, 0)
	for i := len(typedLst) - 1; i > indexVal; i-- {
		typedLst[i] = typedLst[i-1]
	}
	typedLst[indexVal] = elementVal

	return typedLst, nil
}

func assertEqualSlices(got, want []int) bool {
	if len(got) != len(want) {
		return false
	}
	for i := range got {
		if got[i] != want[i] {
			return false
		}
	}
	return true
}

func assertRaises(fn func() ([]int, error), wantErr string) bool {
	_, err := fn()
	if err == nil {
		fmt.Printf("Expected error containing %q but got none\n", wantErr)
		return false
	}
	if err.Error() != wantErr {
		fmt.Printf("Expected error %q but got %q\n", wantErr, err.Error())
		return false
	}
	return true
}

func main() {
	passed := true

	// 1) insert in middle
	res, err := insertElement([]int{1, 2, 3, 4}, 1, 99)
	if err != nil || !assertEqualSlices(res, []int{1, 99, 2, 3, 4}) {
		fmt.Printf("Test 1 failed: got %v, err %v\n", res, err)
		passed = false
	}

	// 2) insert at end
	res, err = insertElement([]int{10, 20, 30}, 3, 40)
	if err != nil || !assertEqualSlices(res, []int{10, 20, 30, 40}) {
		fmt.Printf("Test 2 failed: got %v, err %v\n", res, err)
		passed = false
	}

	// 3) insert at start
	res, err = insertElement([]int{100, 200}, 0, 300)
	if err != nil || !assertEqualSlices(res, []int{300, 100, 200}) {
		fmt.Printf("Test 3 failed: got %v, err %v\n", res, err)
		passed = false
	}

	// 4) insert into empty list
	res, err = insertElement([]int{}, 0, 7)
	if err != nil || !assertEqualSlices(res, []int{7}) {
		fmt.Printf("Test 4 failed: got %v, err %v\n", res, err)
		passed = false
	}

	// 5) negative index must raise
	if !assertRaises(func() ([]int, error) {
		return insertElement([]int{1, 2, 3}, -1, 0)
	}, "index out of range") {
		fmt.Println("Test 5 failed")
		passed = false
	}

	// 6) index too large must raise
	if !assertRaises(func() ([]int, error) {
		return insertElement([]int{1, 2, 3}, 5, 0)
	}, "index out of range") {
		fmt.Println("Test 6 failed")
		passed = false
	}

	// 7) wrong type for index must raise
	if !assertRaises(func() ([]int, error) {
		return insertElement([]int{1, 2, 3}, "1", 9)
	}, "index must be an int") {
		fmt.Println("Test 7 failed")
		passed = false
	}

	// 8) wrong type for lst must raise
	if !assertRaises(func() ([]int, error) {
		return insertElement("not a list", 0, 1)
	}, "lst must be a list") {
		fmt.Println("Test 8 failed")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}