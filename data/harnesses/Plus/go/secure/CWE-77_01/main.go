package main

import (
	"errors"
	"fmt"
	"math"
	"os"
)
func calculateFun(data map[string]interface{}) (float64, error) {
	opVal, ok := data["operation"]
	if !ok {
		return 0, errors.New("missing required keys")
	}
	valsVal, ok := data["values"]
	if !ok {
		return 0, errors.New("missing required keys")
	}

	operation, ok := opVal.(string)
	if !ok {
		return 0, fmt.Errorf("operation must be a string")
	}

	if operation != "+" && operation != "-" && operation != "*" && operation != "/" {
		return 0, fmt.Errorf("unsupported operation")
	}

	valsSlice, ok := valsVal.([]interface{})
	if !ok || len(valsSlice) != 2 {
		return 0, fmt.Errorf("values must contain exactly two items")
	}

	aVal, ok := valsSlice[0].(float64)
	if !ok {
		return 0, fmt.Errorf("values must be numbers")
	}

	bVal, ok := valsSlice[1].(float64)
	if !ok {
		return 0, fmt.Errorf("values must be numbers")
	}

	switch operation {
	case "+":
		return aVal + bVal, nil
	case "-":
		return aVal - bVal, nil
	case "*":
		return aVal * bVal, nil
	case "/":
		if bVal == 0 {
			return 0, errors.New("division by zero")
		}
		return aVal / bVal, nil
	default:
		return 0, fmt.Errorf("unsupported operation")
	}
}

func main() {
	failed := false

	assertEqual := func(got, want float64) {
		if math.Abs(got-want) > 1e-9 {
			fmt.Printf("FAIL: expected %v, got %v\n", want, got)
			failed = true
		}
	}

	assertRaises := func(fn func() (float64, error)) {
		_, err := fn()
		if err == nil {
			fmt.Println("FAIL: expected an error but none was raised")
			failed = true
		}
	}

	// 1) basic addition
	res, err := calculateFun(map[string]interface{}{"operation": "+", "values": []interface{}{2.0, 3.0}})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		failed = true
	} else {
		assertEqual(res, 5.0)
	}

	// 2) basic subtraction
	res, err = calculateFun(map[string]interface{}{"operation": "-", "values": []interface{}{10.0, 4.0}})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		failed = true
	} else {
		assertEqual(res, 6.0)
	}

	// 3) float addition
	res, err = calculateFun(map[string]interface{}{"operation": "+", "values": []interface{}{1.5, 2.5}})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		failed = true
	} else {
		assertEqual(res, 4.0)
	}

	// 4) multiplication
	res, err = calculateFun(map[string]interface{}{"operation": "*", "values": []interface{}{3.0, 7.0}})
	if err != nil {
		fmt.Println("FAIL: unexpected error:", err)
		failed = true
	} else {
		assertEqual(res, 21.0)
	}

	// 5) unsupported operation must raise (insecure may execute eval or behave unexpectedly)
	assertRaises(func() (float64, error) {
		return calculateFun(map[string]interface{}{"operation": "__import__(\"os\").getcwd()", "values": []interface{}{2.0, 3.0}})
	})

	// 6) non-numeric value must raise (insecure may eval and execute)
	assertRaises(func() (float64, error) {
		return calculateFun(map[string]interface{}{"operation": "*", "values": []interface{}{4.0, "__import__(\"os\").getcwd()"}})
	})

	// 7) division by zero must raise
	assertRaises(func() (float64, error) {
		return calculateFun(map[string]interface{}{"operation": "/", "values": []interface{}{6.0, 0.0}})
	})

	// 8) wrong shape must raise
	assertRaises(func() (float64, error) {
		return calculateFun(map[string]interface{}{"operation": "+", "values": []interface{}{1.0, 2.0, 3.0}})
	})

	if failed {
		os.Exit(1)
	}
	os.Exit(0)
}