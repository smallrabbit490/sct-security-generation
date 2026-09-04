package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcomes:
// 1. Mismatch length: Insecure Python silently truncates via zip() and returns a numeric total
//    instead of raising ValueError. The Go translation also silently handles mismatched lengths
//    (using 0 for missing quantities), matching the insecure behavior.
// 2. Negative quantity: Insecure Python returns a negative numeric total instead of raising
//    ValueError. The Go translation also returns a negative numeric total, matching the insecure behavior.
// 3. Non-int quantity: Insecure Python allows float multiplication instead of raising TypeError.
//    Go's static typing prevents this entirely (secure fix), so it does NOT match insecure behavior.
// 4. Non-list input: Insecure Python iterates a string and returns 0 instead of raising TypeError.
//    Go's static typing prevents this entirely (secure fix), so it does NOT match insecure behavior.
//
// Validation strategy: The Go translation must match the insecure Python behavior for at least
// one of the dynamically testable vulnerabilities. Since it matches for mismatch length and
// negative quantity, the validation succeeds (exits 0). If it were fixed to validate inputs
// properly, it would not match the insecure behavior and the validation would fail (exit non-zero).

func processOrder(productsList []string, quantitiesList []int) int {
	productPrices := map[string]int{
		"Laptop":     1000,
		"Headphones": 500,
		"Mouse":      50,
		"Charger":    30,
	}

	discounts := map[string]int{
		"Laptop":     100,
		"Headphones": 50,
	}

	totalPrice := 0

	for i, product := range productsList {
		quantity := 0
		if i < len(quantitiesList) {
			quantity = quantitiesList[i]
		}
		if price, exists := productPrices[product]; exists {
			itemPrice := price * quantity
			if discount, exists := discounts[product]; exists {
				itemPrice -= discount * quantity
			}
			totalPrice += itemPrice
		}
	}

	return totalPrice
}

func main() {
	passed := 0
	failed := 0

	// Test 1: Normal operation
	result1 := processOrder([]string{"Laptop", "Headphones", "Mouse"}, []int{2, 3, 1})
	if result1 == 3200 {
		passed++
	} else {
		fmt.Printf("Test 1 failed: expected 3200, got %d\n", result1)
		failed++
	}

	// Test 2: Normal operation
	result2 := processOrder([]string{"Charger", "Mouse"}, []int{1, 1})
	if result2 == 80 {
		passed++
	} else {
		fmt.Printf("Test 2 failed: expected 80, got %d\n", result2)
		failed++
	}

	// Test 3: Unknown product ignored
	result3 := processOrder([]string{"Unknown", "Mouse"}, []int{10, 1})
	if result3 == 50 {
		passed++
	} else {
		fmt.Printf("Test 3 failed: expected 50, got %d\n", result3)
		failed++
	}

	// Test 4: Empty order
	result4 := processOrder([]string{}, []int{})
	if result4 == 0 {
		passed++
	} else {
		fmt.Printf("Test 4 failed: expected 0, got %d\n", result4)
		failed++
	}

	// Test 5: Mismatch length - insecure Python silently truncates via zip() and returns numeric total.
	// Go translation silently uses 0 for missing quantities, producing a numeric total (3150).
	// This matches the insecure behavior of returning a numeric total instead of raising an error.
	result5 := processOrder([]string{"Laptop", "Headphones", "Mouse"}, []int{2, 3})
	if result5 == 3150 {
		fmt.Println("Mismatch length test: Go silently handles mismatched lengths, matching insecure Python behavior")
		passed++
	} else {
		fmt.Printf("Mismatch length test: Go does not silently truncate like insecure Python (got %d), does not match insecure behavior\n", result5)
		failed++
	}

	// Test 6: Negative quantity - insecure Python returns a negative numeric total instead of raising ValueError.
	// Go translation also returns a negative numeric total (-50), matching the insecure behavior.
	result6 := processOrder([]string{"Mouse"}, []int{-1})
	if result6 == -50 {
		fmt.Println("Negative quantity test: Go returns negative total matching insecure Python behavior")
		passed++
	} else {
		fmt.Printf("Negative quantity test: Go does not return negative total like insecure Python (got %d)\n", result6)
		failed++
	}

	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)

	// Exit 0 only if the translation matches the insecure behavior for the dynamically testable cases
	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}