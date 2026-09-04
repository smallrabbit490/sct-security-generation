package main

import (
	"fmt"
	"os"
	"runtime"
	"sync"
	"time"
)

type Thread struct {
	lock sync.Mutex
}

func getData(dataStart int, dataLimit int, thread *Thread) (int, error) {
	if dataStart < 0 || dataLimit < 0 {
		return 0, fmt.Errorf("value error")
	}

	if thread == nil {
		return 0, fmt.Errorf("type error")
	}

	if dataStart > dataLimit {
		return 0, fmt.Errorf("value error")
	}

	thread.lock.Lock()
	dataStart += 1
	thread.lock.Unlock()

	fmt.Printf("data from A :: %d Accessor thread :: %d\n", dataStart, getGoroutineID())
	time.Sleep(10 * time.Millisecond)
	return dataStart, nil
}

func getGoroutineID() int {
	var buf [64]byte
	n := runtime.Stack(buf[:], false)
	idField := buf[:n]
	// Parse the goroutine ID from the stack output.
	// Example: "goroutine 19 [running]:..."
	var id int64
	_, err := fmt.Sscanf(string(idField), "goroutine %d", &id)
	if err != nil {
		return 0
	}
	return int(id)
}

func main() {
	// Helper function to assert that a call raises an error
	assertRaises := func(fn func() (int, error), shouldPass bool) {
		_, err := fn()
		if shouldPass {
			if err != nil {
				fmt.Printf("FAIL: Expected success but got error: %v\n", err)
				os.Exit(1)
			}
		} else {
			if err == nil {
				fmt.Printf("FAIL: Expected error but got success\n")
				os.Exit(1)
			}
		}
	}

	t := &Thread{}

	// Test 1: Basic functionality
	res, err := getData(0, 10, t)
	if err != nil || res != 1 {
		fmt.Printf("FAIL: Expected (1, nil), got (%d, %v)\n", res, err)
		os.Exit(1)
	}

	// Test 2: Basic functionality
	res, err = getData(1, 10, t)
	if err != nil || res != 2 {
		fmt.Printf("FAIL: Expected (2, nil), got (%d, %v)\n", res, err)
		os.Exit(1)
	}

	// Test 3: must reject start > limit
	assertRaises(func() (int, error) { return getData(11, 10, t) }, false)

	// Test 4: require shared lock container (nil thread)
	assertRaises(func() (int, error) { return getData(0, 10, nil) }, false)

	// Test 5: type checks (string input for int)
	// Note: Go is statically typed, so we cannot pass a string where an int is expected.
	// The Python test `assert_raises(candidate, '0', 10, t, ...)` relies on dynamic typing.
	// In Go, this would be a compile-time error. We simulate the intent by checking logic
	// that might be present if we used interfaces, but here we simply acknowledge the type safety.
	// However, to strictly follow the "Validation rule" of equivalent checks:
	// We can't pass a string to getData(0, 10, t) in Go code.
	// We will skip this specific check as it is enforced by the compiler.

	// Test 6: type checks (too many arguments)
	// Note: Go is statically typed, so passing extra arguments is a compile-time error.
	// We skip this as it is enforced by the compiler.

	fmt.Println("All tests passed.")
}