package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
// removeElement removes the element at position index from lst and returns the modified list.
// It returns an error when it cannot complete the task successfully.
func removeElement(lst interface{}, index interface{}) ([]interface{}, error) {
	// Check if lst is a valid slice
	if lst == nil {
		return nil, errors.New("lst must be a list")
	}
	lstVal := reflect.ValueOf(lst)
	if lstVal.Kind() != reflect.Slice {
		return nil, errors.New("lst must be a list")
	}

	// Check if index is an int
	indexVal := reflect.ValueOf(index)
	if indexVal.Kind() != reflect.Int {
		return nil, errors.New("index must be an int")
	}
	idx := int(indexVal.Int())

	// Check index bounds
	if idx < 0 || idx >= lstVal.Len() {
		return nil, errors.New("index out of range")
	}

	// Convert slice to []interface{}
	interfaceSlice := make([]interface{}, lstVal.Len())
	for i := 0; i < lstVal.Len(); i++ {
		interfaceSlice[i] = lstVal.Index(i).Interface()
	}

	// Remove element at index
	return append(interfaceSlice[:idx], interfaceSlice[idx+1:]...), nil
}

func main() {
	passed := true

	// Helper to check results and fail on mismatch
	assertEqual := func(testName string, got []interface{}, err error, want []interface{}) {
		if err != nil {
			fmt.Printf("%s: unexpected error: %v\n", testName, err)
			passed = false
			return
		}
		if !reflect.DeepEqual(got, want) {
			fmt.Printf("%s: expected %v, got %v\n", testName, want, got)
			passed = false
		}
	}

	// Helper to check that an error is returned
	assertError := func(testName string, err error, wantErr string) {
		if err == nil {
			fmt.Printf("%s: expected error but got nil\n", testName)
			passed = false
			return
		}
		if err.Error() != wantErr {
			fmt.Printf("%s: expected error '%s', got '%s'\n", testName, wantErr, err.Error())
			passed = false
		}
	}

	// 1) remove middle
	got1, err1 := removeElement([]interface{}{1, 2, 3, 4, 5}, 2)
	assertEqual("remove middle", got1, err1, []interface{}{1, 2, 4, 5})

	// 2) remove last
	got2, err2 := removeElement([]interface{}{"a", "b", "c", "d"}, 3)
	assertEqual("remove last", got2, err2, []interface{}{"a", "b", "c"})

	// 3) remove first
	got3, err3 := removeElement([]interface{}{9, 8, 7}, 0)
	assertEqual("remove first", got3, err3, []interface{}{8, 7})

	// 4) single element list
	got4, err4 := removeElement([]interface{}{1}, 0)
	assertEqual("single element", got4, err4, []interface{}{})

	// 5) too large index must raise
	_, err5 := removeElement([]interface{}{1, 2, 3}, 100)
	assertError("too large index", err5, "index out of range")

	// 6) negative index must raise
	_, err6 := removeElement([]interface{}{1, 2, 3}, -1)
	assertError("negative index", err6, "index out of range")

	// 7) non-int index must raise
	_, err7 := removeElement([]interface{}{1, 2, 3}, "1")
	assertError("non-int index", err7, "index must be an int")

	// 8) wrong type for lst must raise
	_, err8 := removeElement("not a list", 0)
	assertError("wrong type for lst", err8, "lst must be a list")

	if !passed {
		os.Exit(1)
	}
	fmt.Println("All tests passed")
}