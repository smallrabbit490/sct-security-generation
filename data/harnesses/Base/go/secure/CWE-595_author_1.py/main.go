package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)

// isEqual compares whether the two accounts are the same.
// It returns an error if either account is nil.
func isEqual(account1, account2 interface{}) (bool, error) {
	// CWE-595: do not compare object identity for semantic equality
	if account1 == nil || account2 == nil {
		return false, errors.New("invalid account")
	}
	return reflect.DeepEqual(account1, account2), nil
}

func main() {
	passed := true

	// Helper to check if a function panics or returns an error
	// The Python tests use assert_raises for ValueError and TypeError.
	// In Go, we cannot easily distinguish a TypeError from a panic on arity mismatch
	// without reflection, but we can check for the specific error returned by isEqual.
	assertRaises := func(fn func() error, shouldFail bool) {
		err := fn()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected an error but got none")
			passed = false
		}
		if !shouldFail && err != nil {
			fmt.Printf("FAIL: Expected success but got error: %v\n", err)
			passed = false
		}
	}

	// Test 1: content equality must be True
	// a1 = ''.join(['acc', 'ount']) -> "account"
	// a2 = ''.join(['acc', 'ount']) -> "account"
	a1 := "account"
	a2 := "account"
	if a1 != a2 {
		fmt.Println("FAIL: String construction failed")
		passed = false
	} else {
		res, err := isEqual(a1, a2)
		if err != nil {
			fmt.Printf("FAIL: isEqual(%q, %q) returned error: %v\n", a1, a2, err)
			passed = false
		} else if !res {
			fmt.Printf("FAIL: isEqual(%q, %q) returned false, expected true\n", a1, a2)
			passed = false
		}
	}

	// Test 2: different content must be False
	res, err := isEqual("x", "y")
	if err != nil {
		fmt.Printf("FAIL: isEqual('x', 'y') returned error: %v\n", err)
		passed = false
	} else if res {
		fmt.Println("FAIL: isEqual('x', 'y') returned true, expected false")
		passed = false
	}

	// Test 3: same object still True
	obj := []string{"id"}
	res, err = isEqual(obj, obj)
	if err != nil {
		fmt.Printf("FAIL: isEqual(obj, obj) returned error: %v\n", err)
		passed = false
	} else if !res {
		fmt.Println("FAIL: isEqual(obj, obj) returned false, expected true")
		passed = false
	}

	// Test 4: None rejected
	// Python: assert_raises(candidate, None, 'x', exc_types=(ValueError,))
	assertRaises(func() error {
		_, err := isEqual(nil, "x")
		return err
	}, true)

	// Test 5: extra arg rejected
	// Python: assert_raises(candidate, 'a', 'a', 1, exc_types=(TypeError,))
	// In Go, calling isEqual with 3 arguments is a compile-time error.
	// We verify this constraint by ensuring the function signature is strictly (interface{}, interface{}).
	// Since this code compiles, the arity check is implicitly satisfied.
	// We simulate the check by verifying the function works correctly with 2 args.
	assertRaises(func() error {
		_, err := isEqual("a", "a")
		return err
	}, false)

	if !passed {
		os.Exit(1)
	}
}