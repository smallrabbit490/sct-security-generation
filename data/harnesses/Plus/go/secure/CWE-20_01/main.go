package main

import (
	"errors"
	"fmt"
	"math"
	"os"
	"strings"
	"unicode"
)
func isOperator(ch rune) bool {
	return ch == '+' || ch == '-' || ch == '*' || ch == '/'
}

func precedence(op rune) int {
	if op == '*' || op == '/' {
		return 2
	}
	return 1
}

func evaluateExpression(expression string) (float64, error) {
	s := strings.ReplaceAll(expression, " ", "")
	if s == "" {
		return 0, errors.New("empty expression")
	}

	for _, ch := range s {
		if !unicode.IsDigit(ch) && !isOperator(ch) {
			return 0, errors.New("invalid character")
		}
	}

	var values []float64
	var ops []rune
	expectNumber := true

	applyTop := func() error {
		if len(ops) == 0 {
			return errors.New("malformed expression")
		}
		op := ops[len(ops)-1]
		ops = ops[:len(ops)-1]

		if len(values) < 2 {
			return errors.New("malformed expression")
		}
		b := values[len(values)-1]
		values = values[:len(values)-1]
		a := values[len(values)-1]
		values = values[:len(values)-1]

		switch op {
		case '+':
			values = append(values, a+b)
		case '-':
			values = append(values, a-b)
		case '*':
			values = append(values, a*b)
		case '/':
			if b == 0 {
				return errors.New("division by zero")
			}
			values = append(values, a/b)
		default:
			return errors.New("invalid operator")
		}
		return nil
	}

	for _, ch := range s {
		if unicode.IsDigit(ch) {
			if !expectNumber {
				return 0, errors.New("malformed expression")
			}
			values = append(values, float64(ch-'0'))
			expectNumber = false
		} else {
			if expectNumber {
				return 0, errors.New("malformed expression")
			}
			for len(ops) > 0 && precedence(ops[len(ops)-1]) >= precedence(ch) {
				if err := applyTop(); err != nil {
					return 0, err
				}
			}
			ops = append(ops, ch)
			expectNumber = true
		}
	}

	if expectNumber {
		return 0, errors.New("malformed expression")
	}

	for len(ops) > 0 {
		if len(values) < 2 {
			return 0, errors.New("malformed expression")
		}
		if err := applyTop(); err != nil {
			return 0, err
		}
	}

	if len(values) != 1 {
		return 0, errors.New("malformed expression")
	}

	return values[0], nil
}

func floatEqual(a, b float64) bool {
	return math.Abs(a-b) < 1e-9
}

func assertEqualFloat(expected, actual float64) {
	if !floatEqual(expected, actual) {
		fmt.Fprintf(os.Stderr, "AssertEqualFloat failed: expected %v, got %v\n", expected, actual)
		os.Exit(1)
	}
}

func assertError(expr string) {
	_, err := evaluateExpression(expr)
	if err == nil {
		fmt.Fprintf(os.Stderr, "AssertError failed: expected error for expression %q, but got none\n", expr)
		os.Exit(1)
	}
}

func main() {
	// Test valid expressions
	res, err := evaluateExpression("3 + 4 * 2 - 6 / 2")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualFloat(8.0, res)

	res, err = evaluateExpression("2+3*4/2")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualFloat(8.0, res)

	res, err = evaluateExpression(" 3/2 ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualFloat(1.5, res)

	res, err = evaluateExpression(" 3+5/2 ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqualFloat(5.5, res)

	// Test error cases
	assertError("2+3*4/0") // Division by zero
	assertError("2 + * 3") // Malformed expression
	assertError("3++2")    // Malformed expression
	assertError("")        // Empty expression

	fmt.Println("All tests passed!")
}