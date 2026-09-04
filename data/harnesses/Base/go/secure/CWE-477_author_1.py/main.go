package main

import (
	"fmt"
	"os"
	"reflect"
	"runtime"
	"time"
)

var startTime = time.Now()

// currentTime returns the current processor time in seconds.
// It mirrors the Python entry point.
func currentTime() float64 {
	var t float64
	if runtime.GOOS == "windows" {
		t = time.Since(startTime).Seconds()
	} else {
		t = float64(time.Since(startTime).Nanoseconds()) / 1e9
	}

	if t < 0 {
		panic("value error: time is negative")
	}

	return t
}

func main() {
	passed := true

	// Test 1: First call returns a non-negative float64
	t1 := currentTime()
	if reflect.TypeOf(t1).Kind() != reflect.Float64 {
		fmt.Fprintf(os.Stderr, "Test 1 Failed: expected float64, got %v\n", reflect.TypeOf(t1).Kind())
		passed = false
	}
	if t1 < 0.0 {
		fmt.Fprintf(os.Stderr, "Test 1 Failed: expected >= 0.0, got %f\n", t1)
		passed = false
	}

	// Test 2: Second call returns a non-negative float64
	t2 := currentTime()
	if reflect.TypeOf(t2).Kind() != reflect.Float64 {
		fmt.Fprintf(os.Stderr, "Test 2 Failed: expected float64, got %v\n", reflect.TypeOf(t2).Kind())
		passed = false
	}
	if t2 < 0.0 {
		fmt.Fprintf(os.Stderr, "Test 2 Failed: expected >= 0.0, got %f\n", t2)
		passed = false
	}

	// Test 3: Function rejects arguments (Go enforces this at compile time, 
	// but we verify the type signature dynamically to match Python's TypeError checks)
	fnType := reflect.TypeOf(currentTime)
	if fnType.NumIn() != 0 {
		fmt.Fprintf(os.Stderr, "Test 3 Failed: expected 0 parameters, got %d\n", fnType.NumIn())
		passed = false
	}
	if fnType.NumOut() != 1 || fnType.Out(0).Kind() != reflect.Float64 {
		fmt.Fprintf(os.Stderr, "Test 3 Failed: expected 1 float64 return value\n")
		passed = false
	}

	// Test 4: Insecure code failure analysis
	// The Python insecure version used time.clock(), which raises AttributeError in modern Python.
	// The secure version uses process_time() (approximated here with time.Since).
	// We ensure our secure implementation successfully returns a valid float64 without panicking.
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(os.Stderr, "Test 4 Failed: secure implementation panicked unexpectedly: %v\n", r)
			os.Exit(1)
		}
	}()
	_ = currentTime()

	if !passed {
		os.Exit(1)
	}
}