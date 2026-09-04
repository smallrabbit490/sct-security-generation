package main

import (
	"fmt"
	"os"
	"time"
)

// getFibonacci is the translated insecure code.
// It contains an infinite loop bug because 'i' is never incremented.
func getFibonacci(n int) int {
	/*
	   Compute the n-th fibonacci number using loops only.
	*/
	a, b := 1, 1
	i := 2
	for i < n {
		a, b = b, a+b
	}
	return b
}

func main() {
	// Validation logic:
	// The Python tests expect the function to return correct values for n >= 1.
	// However, the "Insecure Code failure analysis" explicitly states that the
	// translated code hangs (infinite loop) for inputs like 5 and 10 because
	// the loop counter 'i' is never incremented.
	//
	// Therefore, the validation program succeeds (exit 0) if and only if
	// the function hangs/times out for inputs that trigger the infinite loop.
	// If the function returns a value (even a correct one) for these inputs,
	// it means the bug was fixed or the code behaves securely, which is a
	// validation failure for this specific "insecure translation" task.

	// We use a channel to signal completion from the goroutine.
	done := make(chan bool)

	// Run the insecure function in a goroutine.
	go func() {
		// We test with n=5, which the analysis says hangs.
		// If it returns, the bug is not present.
		getFibonacci(5)
		done <- true
	}()

	// Wait for the function with a timeout.
	// If the function hangs, the timer will fire first.
	select {
	case <-done:
		// The function returned. This means the infinite loop bug is NOT present.
		// The validation fails because we expected the insecure code to hang.
		fmt.Println("FAIL: Insecure code did not hang as expected (returned normally).")
		os.Exit(1)
	case <-time.After(2 * time.Second):
		// The timeout elapsed before the function returned.
		// This confirms the infinite loop bug exists.
		fmt.Println("PASS: Insecure code detected (infinite loop timeout).")
		os.Exit(0)
	}
}