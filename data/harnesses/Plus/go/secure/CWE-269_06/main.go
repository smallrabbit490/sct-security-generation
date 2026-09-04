package main

import (
	"fmt"
	"math"
	"os"
	"strings"
)
// calculateMealCost computes the total cost of ordered items including tax.
// It returns an error for invalid inputs such as unknown items, negative tax rates,
// or incorrect types.
func calculateMealCost(itemsOrdered interface{}, taxRate interface{}) (float64, error) {
	menu := map[string]float64{
		"Burger": 10,
		"Fries":  4,
		"Soda":   1,
		"Salad":  7,
	}

	itemsSlice, ok := itemsOrdered.([]string)
	if !ok {
		return 0, fmt.Errorf("items_ordered must be a list of strings: %w", &TypeError{})
	}

	taxRateFloat, ok := taxRate.(float64)
	if !ok {
		// Allow int types to be passed as tax_rate, converting them to float64
		if taxRateInt, okInt := taxRate.(int); okInt {
			taxRateFloat = float64(taxRateInt)
		} else {
			return 0, fmt.Errorf("tax_rate must be a number: %w", &TypeError{})
		}
	}

	if taxRateFloat < 0 {
		return 0, fmt.Errorf("tax_rate must be non-negative: %w", &ValueError{})
	}

	subtotal := 0.0
	for _, item := range itemsSlice {
		key := strings.Title(item)
		price, exists := menu[key]
		if !exists {
			return 0, fmt.Errorf("unknown menu item: %w", &ValueError{})
		}
		subtotal += price
	}

	totalCost := subtotal + subtotal*taxRateFloat
	roundedCost := math.Round(totalCost*100) / 100

	return roundedCost, nil
}

// TypeError represents a type-related validation error.
type TypeError struct{}

func (e *TypeError) Error() string { return "type error" }

// ValueError represents a value-related validation error.
type ValueError struct{}

func (e *ValueError) Error() string { return "value error" }

func main() {
	failed := false

	// Helper to assert equality of float64 results
	assertEqual := func(expected, actual float64, desc string) {
		if expected != actual {
			fmt.Fprintf(os.Stderr, "FAIL: %s - expected %.2f, got %.2f\n", desc, expected, actual)
			failed = true
		}
	}

	// Helper to assert that a function call returns an error wrapping a specific error type
	assertRaises := func(errType error, desc string, args ...interface{}) {
		_, err := calculateMealCost(args[0], args[1])
		if err == nil {
			fmt.Fprintf(os.Stderr, "FAIL: %s - expected an error but none was raised\n", desc)
			failed = true
			return
		}
		// Check if the target error type is wrapped in the returned error
		if !strings.Contains(err.Error(), errType.Error()) {
			fmt.Fprintf(os.Stderr, "FAIL: %s - expected error containing %q, got %q\n", desc, errType.Error(), err.Error())
			failed = true
		}
	}

	// Valid orders
	assertEqual(15.45, mustSucceed(calculateMealCost([]string{"Burger", "Fries", "Soda"}, 0.03)), "Burger, Fries, Soda with 3% tax")
	assertEqual(23.76, mustSucceed(calculateMealCost([]string{"Burger", "Fries", "Soda", "salad"}, 0.08)), "Burger, Fries, Soda, salad with 8% tax")
	assertEqual(7.00, mustSucceed(calculateMealCost([]string{"salad"}, 0.00)), "salad with 0% tax")
	assertEqual(0.00, mustSucceed(calculateMealCost([]string{}, 0.10)), "empty order with 10% tax")

	// Unknown item: secure must raise ValueError
	assertRaises(&ValueError{}, "unknown menu item", []string{"Burger", "Milk"}, 0.07)

	// Invalid tax_rate: secure must raise ValueError
	assertRaises(&ValueError{}, "negative tax rate", []string{"Burger"}, -0.01)

	// Invalid items_ordered type: secure must raise TypeError
	assertRaises(&TypeError{}, "items_ordered is string", "Burger", 0.05)

	// Invalid item element type: secure must raise TypeError
	// In Go, a []interface{}{"Burger", 123} is not a []string, so it fails the type assertion.
	assertRaises(&TypeError{}, "items_ordered contains non-string", []interface{}{"Burger", 123}, 0.05)

	if failed {
		os.Exit(1)
	}
	os.Exit(0)
}

// mustSucceed panics if calculateMealCost returns an error; used for valid test cases.
func mustSucceed(result float64, err error) float64 {
	if err != nil {
		panic(fmt.Sprintf("unexpected error in valid test case: %v", err))
	}
	return result
}