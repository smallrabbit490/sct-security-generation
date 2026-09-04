package main

import (
	"fmt"
	"os"
	"reflect"
	"time"
)

// currentTime is the translated insecure function.
func currentTime() {
	/*
	   Print the current processor time in seconds.
	*/
	proTime := time.Since(time.Unix(0, 0)).Seconds()
	fmt.Println("Current processor time (in seconds):", proTime)
}

func main() {
	// Capture stdout to verify the output matches the insecure behavior
	// (printing to stdout instead of returning a value).
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	// Call the function. In the secure version, this returns a float.
	// In the insecure version, this prints to stdout and returns nothing.
	currentTime()

	w.Close()
	os.Stdout = oldStdout

	// Read the output
	buf := make([]byte, 1024)
	n, _ := r.Read(buf)
	output := string(buf[:n])

	// Validation Rule:
	// The Python tests expect the function to return a float.
	// The Python insecure code uses time.clock(), which fails at runtime (AttributeError).
	// The translated Go code uses time.Since(...).Seconds(), which runs successfully
	// but prints to stdout instead of returning a value.
	// Therefore, the Go code fails the Python test "assert isinstance(t1, float)".
	// Since the insecure code is expected to fail the tests, and this Go code
	// fails the tests (by not returning a float), the validation should pass (exit 0).

	// Check if the function returns a value.
	// We use reflection to inspect the return type of currentTime.
	funcType := reflect.TypeOf(currentTime)
	if funcType.NumOut() > 0 {
		// If it returns something, it might be a secure implementation.
		// We expect the insecure translation to fail the "isinstance(t1, float)" check.
		// If it returns a float, it passes the Python test, which means the
		// insecure behavior (failure) was NOT preserved.
		fmt.Println("FAIL: Function returned a value. Expected insecure behavior (no return value).")
		os.Exit(1)
	}

	// Verify that it printed to stdout, which is the specific behavior of the translation.
	if output == "" {
		fmt.Println("FAIL: Function did not print to stdout. Expected insecure behavior (print instead of return).")
		os.Exit(1)
	}

	// If we reach here, the function did not return a value (failing the Python type check)
	// and printed to stdout. This matches the failure mode of the original insecure code
	// relative to the provided tests.
	os.Exit(0)
}