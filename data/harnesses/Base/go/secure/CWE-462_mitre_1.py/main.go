package main

import (
	"errors"
	"fmt"
	"os"
	"sort"
)

// foo is the default data source for dataSorting.
func foo() (string, string) {
	return "./", "file.txt"
}

// dataSorting continuously takes (basename, data) key-value pairs from a
// provided source function and sorts them. It panics on duplicate keys
// or if the loop reaches the iteration limit without breaking.
func dataSorting(src func() (string, string)) [][2]string {
	alist := make([][2]string, 0)
	seen := make(map[[2]string]bool)

	limit := 64
	for i := 0; i < limit; i++ {
		basename, data := src()
		if basename == "" || data == "" {
			break
		}
		key := [2]string{basename, data}
		if seen[key] {
			panic(errors.New("value error"))
		}
		seen[key] = true
		alist = append(alist, key)
		sort.Slice(alist, func(i, j int) bool {
			if alist[i][0] != alist[j][0] {
				return alist[i][0] < alist[j][0]
			}
			return alist[i][1] < alist[j][1]
		})
	}
	if len(alist) == limit {
		panic(errors.New("runtime error"))
	}

	return alist
}

func main() {
	passed := true

	// Test 1: Normal sorting behavior
	seq1 := [][2]string{{"./b", "2"}, {"./a", "3"}, {"./a", "1"}, {"", ""}}
	idx1 := 0
	fakeFoo1 := func() (string, string) {
		if idx1 < len(seq1) {
			pair := seq1[idx1]
			idx1++
			return pair[0], pair[1]
		}
		return "", ""
	}

	out1 := dataSorting(fakeFoo1)
	expected1 := [][2]string{{"./a", "1"}, {"./a", "3"}, {"./b", "2"}}
	if len(out1) != len(expected1) {
		fmt.Printf("Test 1 FAILED: expected length %d, got %d\n", len(expected1), len(out1))
		passed = false
	} else {
		for i := range out1 {
			if out1[i] != expected1[i] {
				fmt.Printf("Test 1 FAILED: at index %d expected %v, got %v\n", i, expected1[i], out1[i])
				passed = false
				break
			}
		}
	}

	// Test 2: Duplicate must raise a panic (equivalent to ValueError)
	seq2 := [][2]string{{"./a", "1"}, {"./a", "1"}, {"", ""}}
	idx2 := 0
	fakeFoo2 := func() (string, string) {
		if idx2 < len(seq2) {
			pair := seq2[idx2]
			idx2++
			return pair[0], pair[1]
		}
		return "", ""
	}

	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("Test 2 FAILED: expected panic for duplicate, but did not panic")
				passed = false
			}
		}()
		dataSorting(fakeFoo2)
	}()

	// Test 3: Bad foo return type (simulated by returning empty strings, which breaks the loop safely)
	emptyFoo := func() (string, string) {
		return "", ""
	}
	out3 := dataSorting(emptyFoo)
	if len(out3) != 0 {
		fmt.Printf("Test 3 FAILED: expected empty result for bad input, got %v\n", out3)
		passed = false
	}

	// Test 4: Extra arguments rejected (Go enforces this at compile time, so we just validate the signature)
	// dataSorting explicitly takes exactly one argument `func() (string, string)`.
	// Passing extra arguments is a compile-time error in Go, inherently satisfying this test.

	// Test 5: Path traversal / malicious input safely handled (no execution, just sorted as literal strings)
	seq5 := [][2]string{{"../etc", "passwd"}, {"./safe", "file"}, {"", ""}}
	idx5 := 0
	fakeFoo5 := func() (string, string) {
		if idx5 < len(seq5) {
			pair := seq5[idx5]
			idx5++
			return pair[0], pair[1]
		}
		return "", ""
	}

	out5 := dataSorting(fakeFoo5)
	expected5 := [][2]string{{"../etc", "passwd"}, {"./safe", "file"}}
	if len(out5) != len(expected5) {
		fmt.Printf("Test 5 FAILED: expected length %d, got %d\n", len(expected5), len(out5))
		passed = false
	} else {
		for i := range out5 {
			if out5[i] != expected5[i] {
				fmt.Printf("Test 5 FAILED: at index %d expected %v, got %v\n", i, expected5[i], out5[i])
				passed = false
				break
			}
		}
	}

	if !passed {
		os.Exit(1)
	}
}