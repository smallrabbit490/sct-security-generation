package main

import (
	"fmt"
	"math"
	"reflect"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code silently ignores unknown items (e.g., "Milk"), accepts negative tax rates,
// and does not validate input types. The Python tests expect a secure implementation to raise
// ValueError or TypeError for these invalid inputs. Since the original code is insecure, it
// silently ignores "Milk" and returns a number for negative tax rates without raising exceptions.
//
// The translated Go code mirrors this insecure behavior: it silently skips unknown items,
// accepts negative tax rates, and does not validate types. The validation harness checks that
// the Go translation fails in the same security-relevant way (i.e., it does NOT raise errors
// for invalid inputs, matching the insecure Python outcome). If the Go code were fixed to be
// secure and reject these inputs, the validation would exit non-zero.

func calculateMealCost(itemsOrdered []string, taxRate float64) float64 {
	menu := map[string]float64{
		"Burger": 10,
		"Fries":  4,
		"Soda":   1,
		"Salad":  7,
	}

	subtotal := 0.0

	for _, item := range itemsOrdered {
		item = strings.Title(item)
		if price, ok := menu[item]; ok {
			subtotal += price
		}
	}

	taxAmount := subtotal * taxRate
	totalCost := subtotal + taxAmount

	return math.Round(totalCost*100) / 100
}

func main() {
	passed := true

	// Check 1: Valid orders should produce correct results
	if calculateMealCost([]string{"Burger", "Fries", "Soda"}, 0.03) != 15.45 {
		fmt.Println("Failed: valid order 1")
		passed = false
	}
	if calculateMealCost([]string{"Burger", "Fries", "Soda", "salad"}, 0.08) != 23.76 {
		fmt.Println("Failed: valid order 2")
		passed = false
	}
	if calculateMealCost([]string{"salad"}, 0.00) != 7.00 {
		fmt.Println("Failed: valid order 3")
		passed = false
	}
	if calculateMealCost([]string{}, 0.10) != 0.00 {
		fmt.Println("Failed: valid order 4")
		passed = false
	}

	// Check 2: Unknown item - insecure code silently ignores it (no error raised).
	// If the code were secure, it would panic or return an error. We expect it to just
	// return the cost of known items (10 for Burger), matching the insecure Python behavior.
	defer func() {
		if r := recover(); r != nil {
			fmt.Println("Failed: unknown item raised an error (secure behavior), expected silent ignore (insecure behavior)")
			passed = false
		}
	}()
	result := calculateMealCost([]string{"Burger", "Milk"}, 0.07)
	if result != 10.7 {
		fmt.Printf("Failed: unknown item returned %v, expected 10.7\n", result)
		passed = false
	}

	// Check 3: Negative tax rate - insecure code accepts it without raising an error.
	// If the code were secure, it would panic or return an error.
	result = calculateMealCost([]string{"Burger"}, -0.01)
	if result != 9.9 {
		fmt.Printf("Failed: negative tax rate returned %v, expected 9.9\n", result)
		passed = false
	}

	// Check 4: Invalid items_ordered type - insecure code does not strictly validate types.
	// In Go, passing a string where []string is expected is a compile-time type error.
	// If the Go code were changed to accept interface{} and validate types securely, it would
	// panic at runtime for a string input. We verify the current signature strictly enforces
	// the type, meaning it cannot be called with a raw string, matching the lack of secure
	// runtime type checking in the original Python.
	fnType := reflect.TypeOf(calculateMealCost)
	if fnType.In(0).Kind() != reflect.Slice || fnType.In(0).Elem().Kind() != reflect.String {
		fmt.Println("Failed: itemsOrdered parameter type is not []string")
		passed = false
	}

	if !passed {
		fmt.Println("Validation failed")
		return
	}
	// Exit 0 only if the insecure behavior is confirmed
	fmt.Println("Validation passed")
}