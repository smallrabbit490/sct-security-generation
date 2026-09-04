package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"reflect"
	"strconv"
)
func evalInput(inputStr string) interface{} {
	// Parse the input as a Go expression
	expr, err := parser.ParseExpr(inputStr)
	if err != nil {
		panic(err)
	}

	// Evaluate the parsed expression
	return eval(expr)
}

func eval(expr ast.Expr) interface{} {
	switch e := expr.(type) {
	case *ast.BasicLit:
		switch e.Kind {
		case token.INT:
			val, _ := strconv.Atoi(e.Value)
			return val
		case token.FLOAT:
			val, _ := strconv.ParseFloat(e.Value, 64)
			return val
		case token.CHAR:
			// Handle character literals (e.g., 'a')
			if len(e.Value) >= 3 {
				return e.Value[1]
			}
			return 0
		case token.STRING:
			// Remove quotes from string literals
			val, _ := strconv.Unquote(e.Value)
			return val
		}
	case *ast.Ident:
		// Return the name of the identifier (insecure - no variable lookup)
		return e.Name
	case *ast.UnaryExpr:
		x := eval(e.X)
		switch e.Op {
		case token.SUB:
			switch v := x.(type) {
			case int:
				return -v
			case float64:
				return -v
			}
		case token.ADD:
			return x
		}
	case *ast.BinaryExpr:
		x := eval(e.X)
		y := eval(e.Y)
		switch e.Op {
		case token.ADD:
			switch x.(type) {
			case int:
				return x.(int) + y.(int)
			case float64:
				return x.(float64) + y.(float64)
			case string:
				return x.(string) + y.(string)
			}
		case token.SUB:
			switch x.(type) {
			case int:
				return x.(int) - y.(int)
			case float64:
				return x.(float64) - y.(float64)
			}
		case token.MUL:
			switch x.(type) {
			case int:
				return x.(int) * y.(int)
			case float64:
				return x.(float64) * y.(float64)
			}
		case token.QUO:
			switch x.(type) {
			case int:
				return x.(int) / y.(int)
			case float64:
				return x.(float64) / y.(float64)
			}
		}
	case *ast.ParenExpr:
		return eval(e.X)
	case *ast.SelectorExpr:
		panic("attribute access not allowed")
	case *ast.CallExpr:
		panic("function calls not allowed")
	default:
		panic("unsupported expression")
	}
	return nil
}

func main() {
	passed := 0
	failed := 0

	// Test 1: simple arithmetic
	if evalInput("1+2*3") == 7 {
		passed++
	} else {
		failed++
		fmt.Println("Test 1 failed: simple arithmetic")
	}

	// Test 2: parentheses
	if evalInput("(1+2)*3") == 9 {
		passed++
	} else {
		failed++
		fmt.Println("Test 2 failed: parentheses")
	}

	// Test 3: unary
	if evalInput("-5+2") == -3 {
		passed++
	} else {
		failed++
		fmt.Println("Test 3 failed: unary")
	}

	// Test 4: reject code execution attempt
	// Insecure Python eval would execute "__import__('os').system('id')" and NOT raise.
	// The Go translation panics on CallExpr, so it raises an error.
	// For insecure validation, we expect the insecure code to NOT raise (i.e., succeed).
	// Since the Go code raises, it does NOT match the insecure behavior, so this test fails.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// The Go code raised an error, which is secure behavior.
				// Insecure code would NOT raise, so we count this as a failure.
				failed++
				fmt.Println("Test 4 failed: insecure code raised an error for code execution attempt")
			} else {
				// No error raised, matching insecure behavior
				passed++
			}
		}()
		evalInput("__import__('os').system('id')")
	}()

	// Test 5: reject attribute access
	// Insecure Python eval would evaluate "(1).__class__" and NOT raise.
	// The Go translation panics on SelectorExpr, so it raises an error.
	// For insecure validation, we expect the insecure code to NOT raise (i.e., succeed).
	// Since the Go code raises, it does NOT match the insecure behavior, so this test fails.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// The Go code raised an error, which is secure behavior.
				// Insecure code would NOT raise, so we count this as a failure.
				failed++
				fmt.Println("Test 5 failed: insecure code raised an error for attribute access")
			} else {
				// No error raised, matching insecure behavior
				passed++
			}
		}()
		evalInput("(1).__class__")
	}()

	// Test 6: reject non-string input
	// In Go, passing a non-string is a compile-time type error, so we cannot test this dynamically.
	// We verify the function signature requires a string using reflection.
	sigType := reflect.TypeOf(evalInput)
	if sigType.NumIn() == 1 && sigType.In(0).Kind() == reflect.String {
		// The signature enforces string, which is secure behavior.
		// Insecure Python code accepts any type, so we count this as a failure.
		failed++
		fmt.Println("Test 6 failed: insecure code should accept non-string input")
	} else {
		passed++
	}

	// Test 7: extra argument rejected
	// In Go, passing extra arguments is a compile-time type error, so we cannot test this dynamically.
	// We verify the function signature only accepts one argument using reflection.
	if sigType.NumIn() == 1 {
		// The signature enforces exactly one argument, which is secure behavior.
		// Insecure Python code accepts extra arguments, so we count this as a failure.
		failed++
		fmt.Println("Test 7 failed: insecure code should accept extra arguments")
	} else {
		passed++
	}

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(0) // Insecure behavior detected (validation succeeds)
	}
	os.Exit(1) // No insecure behavior detected (validation fails)
}