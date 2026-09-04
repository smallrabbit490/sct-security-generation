package main

import (
	"errors"
	"fmt"
	"os"
)

// doComputation simulates the function that can be swapped out in the Python tests.
// In Go, we use a variable to hold the function to allow runtime assignment.
var doComputation func() interface{}

func init() {
	// Default implementation matching the Python source
	doComputation = func() interface{} {
		panic(errors.New("Secret info"))
	}
}

// serverBad is the translated entry point.
func serverBad() interface{} {
	// In Go, functions are always defined and callable at compile time,
	// so we skip the runtime check for 'do_computation' existence.
	
	// We must recover from the panic raised by doComputation to simulate the try-except block.
	defer func() {
		if r := recover(); r != nil {
			// The Python code raises a RuntimeError upon catching an exception.
			// We simulate this behavior by panicking with a new error.
			panic(errors.New("runtime error"))
		}
	}()

	return doComputation()
}

func main() {
	// Test 1: do_computation returns 'OK'
	doComputation = func() interface{} { return "OK" }
	if res := serverBad(); res != "OK" {
		fmt.Printf("Test 1 failed: expected 'OK', got %v\n", res)
		os.Exit(1)
	}

	// Test 2: do_computation raises Exception (Secret info)
	// Python: assert_raises(candidate, exc_types=(RuntimeError,))
	doComputation = func() interface{} { panic(errors.New("Secret info")) }
	func() {
		defer func() {
			if r := recover(); r != nil {
				if err, ok := r.(error); ok && err.Error() == "runtime error" {
					// Expected behavior
					return
				}
				fmt.Printf("Test 2 failed: expected 'runtime error', got %v\n", r)
				os.Exit(1)
			}
			fmt.Println("Test 2 failed: expected panic but did not get one")
			os.Exit(1)
		}()
		serverBad()
	}()

	// Test 3: do_computation returns 123
	doComputation = func() interface{} { return 123 }
	if res := serverBad(); res != 123 {
		fmt.Printf("Test 3 failed: expected 123, got %v\n", res)
		os.Exit(1)
	}

	// Test 4: do_computation is missing (nil)
	// Python: g.pop('do_computation') -> assert_raises(candidate, exc_types=(RuntimeError,))
	// In Go, calling a nil function pointer panics. We catch it and raise RuntimeError.
	doComputation = nil
	func() {
		defer func() {
			if r := recover(); r != nil {
				if err, ok := r.(error); ok && err.Error() == "runtime error" {
					// Expected behavior
					return
				}
				fmt.Printf("Test 4 failed: expected 'runtime error', got %v\n", r)
				os.Exit(1)
			}
			fmt.Println("Test 4 failed: expected panic but did not get one")
			os.Exit(1)
		}()
		serverBad()
	}()

	// All tests passed
}