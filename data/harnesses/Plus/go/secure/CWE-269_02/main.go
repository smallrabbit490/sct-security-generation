package main

import (
	"errors"
	"fmt"
	"os"
)
func reserveTickets(age, numTickets interface{}) (int, error) {
	ageInt, ok := age.(int)
	if !ok {
		return 0, errors.New("age and num_tickets must be integers")
	}
	numTicketsInt, ok := numTickets.(int)
	if !ok {
		return 0, errors.New("age and num_tickets must be integers")
	}

	if ageInt < 0 || numTicketsInt <= 0 {
		return 0, errors.New("age and num_tickets must be positive")
	}

	var price int
	if ageInt < 12 {
		price = 20
	} else if ageInt < 65 {
		price = 50
	} else {
		price = 40
	}

	total := price * numTicketsInt

	if numTicketsInt >= 10 {
		total = int(float64(total) * 0.9)
	} else if numTicketsInt >= 5 {
		total = int(float64(total) * 0.95)
	}

	return total, nil
}

func main() {
	passed := true

	assertEqual := func(expected, got int) {
		if expected != got {
			fmt.Printf("FAIL: expected %d, got %d\n", expected, got)
			passed = false
		}
	}

	assertError := func(err error, msg string) {
		if err == nil {
			fmt.Printf("FAIL: %s expected error, got none\n", msg)
			passed = false
		}
	}

	// normal pricing (no discount)
	res, err := reserveTickets(8, 3)
	if err != nil {
		fmt.Printf("FAIL: reserveTickets(8, 3) unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(60, res)
	}

	res, err = reserveTickets(45, 2)
	if err != nil {
		fmt.Printf("FAIL: reserveTickets(45, 2) unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(100, res)
	}

	// 5% discount boundary
	res, err = reserveTickets(45, 5)
	if err != nil {
		fmt.Printf("FAIL: reserveTickets(45, 5) unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(237, res)
	}

	res, err = reserveTickets(11, 9)
	if err != nil {
		fmt.Printf("FAIL: reserveTickets(11, 9) unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(171, res)
	}

	// 10% discount boundary
	res, err = reserveTickets(70, 10)
	if err != nil {
		fmt.Printf("FAIL: reserveTickets(70, 10) unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(360, res)
	}

	res, err = reserveTickets(70, 12)
	if err != nil {
		fmt.Printf("FAIL: reserveTickets(70, 12) unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(432, res)
	}

	// invalid: negative age must return error
	_, err = reserveTickets(-5, 3)
	assertError(err, "reserveTickets(-5, 3)")

	// invalid type: string num_tickets must return error
	_, err = reserveTickets(30, "2")
	assertError(err, "reserveTickets(30, \"2\")")

	if !passed {
		os.Exit(1)
	}
}