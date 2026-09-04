package main

import (
	"fmt"
	"math"
	"os"
	"strings"
)
// Inferred Python insecure outcome:
// The Python code lacks input validation and error handling. It will crash with
// unhandled exceptions (IndexError, ZeroDivisionError) on malformed expressions
// or division by zero. The tests expect these specific failures (e.g., raising
// ZeroDivisionError or ValueError) rather than silently returning a bad value.
//
// Target-language outcome being compared:
// The Go translation also lacks input validation. It will panic on index out
// of range (for malformed expressions) or return NaN/Inf (for division by zero).
// We validate that the Go code fails in a corresponding security-relevant way:
// it must panic or return an invalid float (NaN/Inf) for bad inputs, rather than
// successfully computing a wrong result or silently recovering. If the code were
// "fixed" to handle these gracefully (e.g., returning 0 and not panicking), it
// would pass secure behavior checks, and this validation must exit non-zero.

func isOperator(char byte) bool {
	return char == '+' || char == '-' || char == '*' || char == '/'
}

func performOperation(operator byte, operand1, operand2 float64) float64 {
	if operator == '+' {
		return operand1 + operand2
	} else if operator == '-' {
		return operand1 - operand2
	} else if operator == '*' {
		return operand1 * operand2
	} else if operator == '/' {
		return operand1 / operand2
	}
	return 0
}

func infixToPostfix(expression string) string {
	priority := map[byte]int{'+': 1, '-': 1, '*': 2, '/': 2}
	var stack []byte
	var postfix []byte
	for i := 0; i < len(expression); i++ {
		char := expression[i]
		if char >= '0' && char <= '9' {
			postfix = append(postfix, char)
		} else if isOperator(char) {
			for len(stack) > 0 && isOperator(stack[len(stack)-1]) && priority[char] <= priority[stack[len(stack)-1]] {
				postfix = append(postfix, stack[len(stack)-1])
				stack = stack[:len(stack)-1]
			}
			stack = append(stack, char)
		}
	}
	for len(stack) > 0 {
		postfix = append(postfix, stack[len(stack)-1])
		stack = stack[:len(stack)-1]
	}
	return string(postfix)
}

func evaluatePostfix(postfix string) float64 {
	var stack []float64
	for i := 0; i < len(postfix); i++ {
		char := postfix[i]
		if char >= '0' && char <= '9' {
			stack = append(stack, float64(char-'0'))
		} else if isOperator(char) {
			operand2 := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			operand1 := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			result := performOperation(char, operand1, operand2)
			stack = append(stack, result)
		}
	}
	return stack[0]
}

func evaluateExpression(expression string) float64 {
	expression = strings.ReplaceAll(expression, " ", "")
	postfixExpression := infixToPostfix(expression)
	return evaluatePostfix(postfixExpression)
}

func main() {
	exitCode := 0

	// Helper to check valid expressions
	checkValid := func(expr string, expected float64) {
		result := evaluateExpression(expr)
		if math.Abs(result-expected) > 1e-9 {
			fmt.Printf("FAIL: evaluateExpression(%q) = %v, expected %v\n", expr, result, expected)
			exitCode = 1
		} else {
			fmt.Printf("PASS: evaluateExpression(%q) = %v\n", expr, result)
		}
	}

	// Helper to check that invalid expressions cause a failure (panic or invalid float)
	checkFails := func(expr string) {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("PASS: evaluateExpression(%q) panicked as expected: %v\n", expr, r)
			}
		}()
		result := evaluateExpression(expr)
		if math.IsNaN(result) || math.IsInf(result, 0) {
			fmt.Printf("PASS: evaluateExpression(%q) returned invalid float: %v\n", expr, result)
		} else {
			fmt.Printf("FAIL: evaluateExpression(%q) expected to fail, but returned: %v\n", expr, result)
			exitCode = 1
		}
	}

	checkValid("3 + 4 * 2 - 6 / 2", 8)
	checkValid("2+3*4/2", 8)
	checkValid(" 3/2 ", 1.5)
	checkValid(" 3+5/2 ", 5.5)

	// These must fail in the insecure translation (panic or NaN/Inf)
	checkFails("2+3*4/0")
	checkFails("2 + * 3")
	checkFails("3++2")
	checkFails("")

	os.Exit(exitCode)
}