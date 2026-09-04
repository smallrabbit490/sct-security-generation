package main

import (
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
	"unicode"
)
// Operator precedence map
var precedence = map[rune]int{
	'+': 1,
	'-': 1,
	'*': 2,
	'/': 2,
}

func applyOp(a, b float64, op rune) (float64, error) {
	switch op {
	case '+':
		return a + b, nil
	case '-':
		return a - b, nil
	case '*':
		return a * b, nil
	case '/':
		if b == 0 {
			return 0, fmt.Errorf("division by zero")
		}
		return a / b, nil
	}
	return 0, fmt.Errorf("invalid operator")
}

func applyTopOps(vals *[]float64, ops *[]rune) error {
	if len(*vals) < 2 || len(*ops) == 0 {
		return fmt.Errorf("invalid expression")
	}
	b := (*vals)[len(*vals)-1]
	*vals = (*vals)[:len(*vals)-1]
	a := (*vals)[len(*vals)-1]
	*vals = (*vals)[:len(*vals)-1]
	op := (*ops)[len(*ops)-1]
	*ops = (*ops)[:len(*ops)-1]
	res, err := applyOp(a, b, op)
	if err != nil {
		return err
	}
	*vals = append(*vals, res)
	return nil
}

func evaluateExpression(expression interface{}) (float64, error) {
	expr, ok := expression.(string)
	if !ok {
		return 0, fmt.Errorf("expression must be a string")
	}

	if strings.TrimSpace(expr) == "" {
		return 0, fmt.Errorf("empty expression")
	}

	allowedChars := "0123456789+-*/() "
	for _, ch := range expr {
		if !strings.ContainsRune(allowedChars, ch) {
			return 0, fmt.Errorf("invalid character")
		}
	}

	var vals []float64
	var ops []rune

	i := 0
	for i < len(expr) {
		ch := rune(expr[i])

		if unicode.IsSpace(ch) {
			i++
			continue
		}

		if ch == '(' {
			ops = append(ops, ch)
			i++
		} else if ch == ')' {
			for len(ops) > 0 && ops[len(ops)-1] != '(' {
				if err := applyTopOps(&vals, &ops); err != nil {
					return 0, err
				}
			}
			if len(ops) == 0 {
				return 0, fmt.Errorf("mismatched parentheses")
			}
			ops = ops[:len(ops)-1] // pop '('
			i++
		} else if ch == '+' || ch == '-' || ch == '*' || ch == '/' {
			// Handle unary minus/plus
			if i == 0 || expr[i-1] == '(' {
				if ch == '-' {
					vals = append(vals, 0)
				} else if ch == '+' {
					i++
					continue
				}
			}
			for len(ops) > 0 && ops[len(ops)-1] != '(' && precedence[ops[len(ops)-1]] >= precedence[ch] {
				if err := applyTopOps(&vals, &ops); err != nil {
					return 0, err
				}
			}
			ops = append(ops, ch)
			i++
		} else if unicode.IsDigit(ch) {
			j := i
			for j < len(expr) && (unicode.IsDigit(rune(expr[j])) || rune(expr[j]) == '.') {
				j++
			}
			numStr := expr[i:j]
			val, err := strconv.ParseFloat(numStr, 64)
			if err != nil {
				return 0, fmt.Errorf("invalid number")
			}
			vals = append(vals, val)
			i = j
		} else {
			return 0, fmt.Errorf("invalid character")
		}
	}

	for len(ops) > 0 {
		if ops[len(ops)-1] == '(' {
			return 0, fmt.Errorf("mismatched parentheses")
		}
		if err := applyTopOps(&vals, &ops); err != nil {
			return 0, err
		}
	}

	if len(vals) != 1 {
		return 0, fmt.Errorf("invalid expression")
	}

	return vals[0], nil
}

func main() {
	passed := true

	assertEqual := func(expr string, expected float64) {
		result, err := evaluateExpression(expr)
		if err != nil {
			fmt.Printf("FAIL: evaluateExpression(%q) returned error: %v, expected %v\n", expr, err, expected)
			passed = false
			return
		}
		if math.Abs(result-expected) > 1e-9 {
			fmt.Printf("FAIL: evaluateExpression(%q) = %v, expected %v\n", expr, result, expected)
			passed = false
		} else {
			fmt.Printf("PASS: evaluateExpression(%q) = %v\n", expr, expected)
		}
	}

	assertRaises := func(expr interface{}, expectedErr string) {
		_, err := evaluateExpression(expr)
		if err == nil {
			fmt.Printf("FAIL: evaluateExpression(%v) expected error containing %q, but got nil\n", expr, expectedErr)
			passed = false
			return
		}
		if !strings.Contains(err.Error(), expectedErr) {
			fmt.Printf("FAIL: evaluateExpression(%v) expected error containing %q, but got %q\n", expr, expectedErr, err.Error())
			passed = false
		} else {
			fmt.Printf("PASS: evaluateExpression(%v) raised error: %v\n", expr, err)
		}
	}

	// Valid expressions
	assertEqual("2 + 3 * (5 - 1)", 14)
	assertEqual("(4 + 2) / 3", 2)
	assertEqual(" 10/(2+3) ", 2)
	assertEqual("7 - (2*3) + 1", 2)

	// Error cases
	assertRaises("(4 + 2) / 0", "division by zero")
	assertRaises("(4 + 2) / 3; open('file.txt')", "invalid character")
	assertRaises("1+1; ls -l", "invalid character")
	assertRaises("", "empty expression")

	if !passed {
		os.Exit(1)
	}
}