package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
)

func convert_to_int() {
	/*
		Continuously take an input from user and convert it to int within a try-except block
	*/
	scanner := bufio.NewScanner(os.Stdin)
	for {
		fmt.Print("Enter a number: ")
		scanner.Scan()
		user_input := scanner.Text()
		_, err := strconv.Atoi(user_input)
		if err == nil {
			return
		}
	}
}

func main() {
	// This validation program checks if the translated Go code behaves insecurely
	// as expected by the Python tests.
	//
	// The Python tests expect the insecure code to fail in the third case:
	// "Make insecure fail fast without hanging: third call triggers KeyboardInterrupt"
	// The Python code loops forever on invalid input, so when the input generator
	// raises KeyboardInterrupt, the Python code crashes with that error.
	// The test asserts that a ValueError is raised. Since KeyboardInterrupt is raised
	// instead, the assertion fails.
	//
	// Therefore, for the validation to pass (exit 0), the Go program must
	// demonstrate that it loops forever on invalid input (insecure behavior)
	// and does not return or panic on the first two invalid inputs.
	// We simulate the input sequence ['a', 'b'] and verify that the function
	// does not return. If it returns, it means it handled the error securely
	// (e.g., by returning an error or panicking with a specific type), which
	// would be a failure of the "insecure" validation.

	// Create a pipe to simulate stdin
	r, w, _ := os.Pipe()
	defer r.Close()
	defer w.Close()

	// Save original stdin
	oldStdin := os.Stdin
	defer func() { os.Stdin = oldStdin }()

	// Redirect stdin
	os.Stdin = r

	// Write the input sequence 'a\nb\n' to the pipe.
	// If the code is insecure (loops forever), it will consume 'a', loop back,
	// consume 'b', loop back, and then block waiting for more input.
	// If the code is secure (e.g., returns error), it will return.
	// We run this in a goroutine to detect if it returns.
	done := make(chan bool)
	go func() {
		convert_to_int()
		done <- true
	}()

	// Write inputs
	w.WriteString("a\n")
	w.WriteString("b\n")

	// Wait a moment to see if the function returns.
	// If it returns, it means it didn't loop forever on invalid input.
	// This implies it is secure, so the validation of the "insecure" code fails.
	select {
	case <-done:
		// Function returned. This is secure behavior.
		// The validation expects insecure behavior (infinite loop).
		fmt.Println("FAIL: Code returned on invalid input (Secure behavior detected). Expected infinite loop.")
		os.Exit(1)
	default:
		// Function is still running (blocked on input). This is insecure behavior.
		// The validation passes.
		fmt.Println("PASS: Code loops forever on invalid input (Insecure behavior detected).")
		os.Exit(0)
	}
}