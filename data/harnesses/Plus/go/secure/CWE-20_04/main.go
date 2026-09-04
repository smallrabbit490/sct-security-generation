package main

import (
	"errors"
	"fmt"
	"os"
	"reflect"
)
func processOrder(productsList interface{}, quantitiesList interface{}) (int, error) {
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

	// Type check: inputs must be slices
	productsVal := reflect.ValueOf(productsList)
	quantitiesVal := reflect.ValueOf(quantitiesList)

	if productsVal.Kind() != reflect.Slice {
		return 0, errors.New("products_list must be a list")
	}
	if quantitiesVal.Kind() != reflect.Slice {
		return 0, errors.New("quantities_list must be a list")
	}

	if productsVal.Len() != quantitiesVal.Len() {
		return 0, errors.New("products_list and quantities_list must have the same length")
	}

	// Type check and validate quantities
	for i := 0; i < quantitiesVal.Len(); i++ {
		qVal := quantitiesVal.Index(i)
		if qVal.Kind() != reflect.Int {
			return 0, errors.New("quantities must be integers")
		}
		if int(qVal.Int()) < 0 {
			return 0, errors.New("quantities must be non-negative")
		}
	}

	totalPrice := 0
	for i := 0; i < productsVal.Len(); i++ {
		pVal := productsVal.Index(i)
		if pVal.Kind() != reflect.String {
			continue
		}
		product := pVal.String()
		if price, exists := productPrices[product]; exists {
			discount := discounts[product]
			quantity := int(quantitiesVal.Index(i).Int())
			totalPrice += (price - discount) * quantity
		}
	}
	return totalPrice, nil
}

func main() {
	passed := true

	assertEqual := func(got, want int) {
		if got != want {
			fmt.Printf("FAIL: expected %d, got %d\n", want, got)
			passed = false
		}
	}

	assertError := func(err error) {
		if err == nil {
			fmt.Println("FAIL: expected an error but none was raised")
			passed = false
		}
	}

	// Test 1: Standard order
	total, err := processOrder([]string{"Laptop", "Headphones", "Mouse"}, []int{2, 3, 1})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		passed = false
	} else {
		assertEqual(total, 3200)
	}

	// Test 2: Another standard order
	total, err = processOrder([]string{"Charger", "Mouse"}, []int{1, 1})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		passed = false
	} else {
		assertEqual(total, 80)
	}

	// Test 3: Unknown product is ignored
	total, err = processOrder([]string{"Unknown", "Mouse"}, []int{10, 1})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		passed = false
	} else {
		assertEqual(total, 50)
	}

	// Test 4: Empty order
	total, err = processOrder([]string{}, []int{})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		passed = false
	} else {
		assertEqual(total, 0)
	}

	// Test 5: Mismatch length should raise error
	_, err = processOrder([]string{"Laptop", "Headphones", "Mouse"}, []int{2, 3})
	assertError(err)

	// Test 6: Negative quantity should raise error
	_, err = processOrder([]string{"Mouse"}, []int{-1})
	assertError(err)

	// Test 7: Non-int quantity should raise error
	_, err = processOrder([]string{"Mouse"}, []float64{1.5})
	assertError(err)

	// Test 8: Non-list products_list should raise error
	_, err = processOrder("Laptop", []int{1})
	assertError(err)

	// Test 9: Non-list quantities_list should raise error
	_, err = processOrder([]string{"Laptop"}, "1")
	assertError(err)

	if !passed {
		os.Exit(1)
	}
}