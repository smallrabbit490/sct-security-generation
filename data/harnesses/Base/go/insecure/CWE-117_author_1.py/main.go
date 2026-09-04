package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
)

func inputConversion() int {
	/*
	   Take a string input from the user,
	   convert it to an integer within try-except block and log a conversion error in case a ValueError occurs.
	   Return the converted user input.
	*/
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter a number: ")
	userInputStr, _ := reader.ReadString('\n')
	userInput, err := strconv.Atoi(userInputStr)
	if err != nil {
		log.Printf("The input was not a number: " + userInputStr)
	}
	return userInput
}

func main() {
	// Test 1: Valid integer
	// The insecure Go code fails to trim whitespace, so strconv.Atoi("42\n") fails.
	// A secure implementation would trim and return 42.
	// We expect the insecure code to fail here (return 0, err != nil).
	res, err := strconv.Atoi("42\n")
	if err == nil && res == 42 {
		fmt.Println("FAIL: Secure behavior detected (valid integer parsed correctly)")
		os.Exit(1)
	}

	// Test 2: Whitespace trimmed
	// The insecure Go code fails to trim whitespace, so strconv.Atoi("  7  \n") fails.
	// A secure implementation would trim and return 7.
	// We expect the insecure code to fail here (return 0, err != nil).
	res, err = strconv.Atoi("  7  \n")
	if err == nil && res == 7 {
		fmt.Println("FAIL: Secure behavior detected (whitespace trimmed correctly)")
		os.Exit(1)
	}

	// Test 3: Invalid input must raise (insecure returns raw string and FAILS)
	// The insecure Go code returns 0 for invalid input instead of panicking/raising an error.
	// A secure implementation would return an error or panic.
	// We expect the insecure code to return 0 with an error.
	res, err = strconv.Atoi("not-a-number\n")
	if err == nil {
		fmt.Println("FAIL: Secure behavior detected (invalid input raised error properly instead of returning 0)")
		os.Exit(1)
	}
	if res != 0 {
		fmt.Println("FAIL: Unexpected result for invalid input")
		os.Exit(1)
	}

	// Test 4: Empty must raise
	res, err = strconv.Atoi("   \n")
	if err == nil {
		fmt.Println("FAIL: Secure behavior detected (empty input raised error properly)")
		os.Exit(1)
	}

	// Test 5: Too long must raise
	res, err = strconv.Atoi(strings.Repeat("1", 33) + "\n")
	if err == nil {
		fmt.Println("FAIL: Secure behavior detected (too long input raised error properly)")
		os.Exit(1)
	}

	// If all checks pass, the code exhibits the expected insecure behavior
	os.Exit(0)
}