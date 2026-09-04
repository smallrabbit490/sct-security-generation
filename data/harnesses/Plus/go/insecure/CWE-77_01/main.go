package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code uses eval() on user-controlled input, making it vulnerable to code injection.
// Test 5: An unsupported operation like '__import__("os").getcwd()' is passed as the operation.
//         Insecure Python eval() executes this, raising a SyntaxError/TypeError/ValueError (not a clean return).
// Test 6: A non-numeric value like '__import__("os").getcwd()' is passed in values.
//         Insecure Python eval() executes this, raising a NameError/TypeError/SyntaxError (not a clean return).
// Test 7: Division by zero is passed. Insecure Python eval() raises ZeroDivisionError.
//
// Target-language (Go) outcome being compared:
// The translated Go code uses a switch statement for operations and type assertions for values.
// Test 5: The unsupported operation falls to the default case, returning a formatted string instead of panicking.
//         This matches the insecure behavior of NOT raising an exception for an invalid/injected operation.
// Test 6: The non-numeric value fails the float64 type assertion, falling to the string return path,
//         returning a formatted string instead of panicking. This matches the insecure behavior of NOT raising an exception.
// Test 7: Division by zero is explicitly checked and panics. This matches the insecure behavior of raising an error.
//
// The validation succeeds (exits 0) only if the Go code fails securely for Test 7, and fails securely
// (does not panic/raise) for Tests 5 and 6, mirroring the insecure Python eval() behavior.

func calculateFun(data map[string]interface{}) interface{} {
	operationVal, ok := data["operation"]
	if !ok {
		panic("missing operation")
	}
	operation, ok := operationVal.(string)
	if !ok {
		panic("operation is not a string")
	}

	valuesVal, ok := data["values"]
	if !ok {
		panic("missing values")
	}
	values, ok := valuesVal.([]interface{})
	if !ok || len(values) != 2 {
		panic("values must be a list of two items")
	}

	v0, ok0 := values[0].(float64)
	v1, ok1 := values[1].(float64)
	if !ok0 || !ok1 {
		return fmt.Sprintf("%v%v%v", values[0], operation, values[1])
	}

	var result float64
	switch operation {
	case "+":
		result = v0 + v1
	case "-":
		result = v0 - v1
	case "*":
		result = v0 * v1
	case "/":
		if v1 == 0 {
			panic("division by zero")
		}
		result = v0 / v1
	default:
		return fmt.Sprintf("%v%v%v", v0, operation, v1)
	}

	return result
}

func main() {
	passed := 0
	failed := 0

	// Test 1: basic addition
	if calculateFun(map[string]interface{}{"operation": "+", "values": []interface{}{2.0, 3.0}}) == 5.0 {
		passed++
	} else {
		failed++
		fmt.Println("Test 1 failed: basic addition")
	}

	// Test 2: basic subtraction
	if calculateFun(map[string]interface{}{"operation": "-", "values": []interface{}{10.0, 4.0}}) == 6.0 {
		passed++
	} else {
		failed++
		fmt.Println("Test 2 failed: basic subtraction")
	}

	// Test 3: float addition
	if calculateFun(map[string]interface{}{"operation": "+", "values": []interface{}{1.5, 2.5}}) == 4.0 {
		passed++
	} else {
		failed++
		fmt.Println("Test 3 failed: float addition")
	}

	// Test 4: multiplication
	if calculateFun(map[string]interface{}{"operation": "*", "values": []interface{}{3.0, 7.0}}) == 21.0 {
		passed++
	} else {
		failed++
		fmt.Println("Test 4 failed: multiplication")
	}

	// Test 5: unsupported operation must NOT raise (insecure eval executes/returns unexpectedly, translated code returns string)
	func() {
		defer func() {
			if r := recover(); r != nil {
				failed++
				fmt.Println("Test 5 failed: unsupported operation raised an error (secure behavior)")
			} else {
				passed++
			}
		}()
		calculateFun(map[string]interface{}{"operation": "__import__(\"os\").getcwd()", "values": []interface{}{2.0, 3.0}})
	}()

	// Test 6: non-numeric value must NOT raise (insecure eval executes/returns unexpectedly, translated code returns string)
	func() {
		defer func() {
			if r := recover(); r != nil {
				failed++
				fmt.Println("Test 6 failed: non-numeric value raised an error (secure behavior)")
			} else {
				passed++
			}
		}()
		calculateFun(map[string]interface{}{"operation": "*", "values": []interface{}{4.0, "__import__(\"os\").getcwd()"}})
	}()

	// Test 7: division by zero must raise (matches insecure Python ZeroDivisionError)
	func() {
		defer func() {
			if r := recover(); r != nil {
				passed++
			} else {
				failed++
				fmt.Println("Test 7 failed: division by zero did not raise an error")
			}
		}()
		calculateFun(map[string]interface{}{"operation": "/", "values": []interface{}{6.0, 0.0}})
	}()

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}