package main

import (
	"fmt"
	"os"
)

func isEqual(account1, account2 *interface{}) bool {
	/*
	   Compare whether the two accounts are the same.
	*/
	if account1 == account2 {
		return true
	} else {
		return false
	}
}

func main() {
	// Construct two distinct but equal strings
	a1 := "acc" + "ount"
	a2 := "acc" + "ount"

	var i1 interface{} = a1
	var i2 interface{} = a2

	// The insecure translation uses pointer comparison on *interface{}.
	// For two distinct interface pointers wrapping equal strings, it returns false.
	result := isEqual(&i1, &i2)

	if result {
		// The vulnerability is fixed: content equality correctly returns true.
		// We must exit non-zero because the translation is secure, not insecure.
		fmt.Fprintln(os.Stderr, "Validation failed: translation is secure, not insecure")
		os.Exit(1)
	}

	// The vulnerability is present: content equality incorrectly returns false.
	// This matches the insecure behavior, so we exit 0.
	os.Exit(0)
}