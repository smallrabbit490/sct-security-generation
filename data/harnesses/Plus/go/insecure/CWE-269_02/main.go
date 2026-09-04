package main

import (
	"errors"
	"fmt"
	"os"
)
// reserveTickets computes the total ticket cost based on age and number of tickets.
// Insecure behavior: It does not validate negative ages or non-integer ticket counts,
// allowing invalid inputs to produce a numeric result instead of raising an error.
func reserveTickets(age int, numTickets int) (int, error) {
	ticketPrices := map[string]int{
		"Children": 20,
		"Adults":   50,
		"Seniors":  40,
	}

	totalCost := 0

	var ticketType string
	if age < 12 {
		ticketType = "Children"
	} else if age < 65 {
		ticketType = "Adults"
	} else {
		ticketType = "Seniors"
	}

	totalCost += ticketPrices[ticketType] * numTickets

	// Apply bulk purchase discount
	if numTickets >= 5 {
		if numTickets >= 10 {
			totalCost = int(float64(totalCost) * 0.9)
		} else {
			totalCost = int(float64(totalCost) * 0.95)
		}
	}

	if totalCost == 0 && numTickets > 0 {
		return 0, errors.New("cannot complete task successfully")
	}

	return totalCost, nil
}

func main() {
	failed := false

	// Helper to check expected successful outcomes
	check := func(age, numTickets, expected int) {
		result, err := reserveTickets(age, numTickets)
		if err != nil {
			fmt.Printf("FAIL: reserveTickets(%d, %d) returned error %v, expected %d\n", age, numTickets, err, expected)
			failed = true
			return
		}
		if result != expected {
			fmt.Printf("FAIL: reserveTickets(%d, %d) = %d, expected %d\n", age, numTickets, result, expected)
			failed = true
		}
	}

	// Helper to check expected insecure failure (returns a value instead of an error)
	// Inferred Python insecure outcome: candidate(-5, 3) returns a number instead of raising ValueError.
	// Target-language outcome being compared: reserveTickets(-5, 3) returns a number (no error) instead of returning an error.
	checkInsecure := func(age, numTickets int) {
		result, err := reserveTickets(age, numTickets)
		if err != nil {
			fmt.Printf("FAIL: reserveTickets(%d, %d) returned error %v, but insecure code should return a value\n", age, numTickets, err)
			failed = true
			return
		}
		// If it returns a value without error, the insecure behavior is matched successfully.
		fmt.Printf("INFO: reserveTickets(%d, %d) insecurely returned %d instead of an error\n", age, numTickets, result)
	}

	// Normal pricing (no discount)
	check(8, 3, 60)
	check(45, 2, 100)

	// 5% discount boundary
	check(45, 5, 237)
	check(11, 9, 171)

	// 10% discount boundary
	check(70, 10, 360)
	check(70, 12, 432)

	// Invalid: insecure returns a number; secure must raise.
	// The translated Go code accepts int, so passing -5 is valid at compile-time.
	// The insecure behavior is that it computes and returns a value (-60) instead of an error.
	checkInsecure(-5, 3)

	// Invalid type: insecure computes/returns; secure must raise.
	// In Go, passing a string like "2" for an int parameter is a compile-time type error.
	// The insecure Python code would compute and return a value. Since we cannot represent
	// this invalid type call in Go without a compile-time error, we skip the explicit check
	// but acknowledge the insecure behavior would be to compute/return if it were dynamically typed.

	if failed {
		os.Exit(1)
	}

	os.Exit(0)
}