package main

import (
	"fmt"
	"regexp"
	"strings"
)
func evaluateExpressions(text string) (string, error) {
	pattern := `\{\{([^{}]+)\}\}`
	re, err := regexp.Compile(pattern)
	if err != nil {
		return "", fmt.Errorf("invalid input: %w", err)
	}

	allowed := "0123456789+-*/() "

	safeEval := func(expr string) (string, error) {
		trimmed := strings.TrimSpace(expr)
		if trimmed == "" {
			return "", fmt.Errorf("empty expression")
		}
		for _, ch := range expr {
			if !strings.ContainsRune(allowed, ch) {
				return "", fmt.Errorf("invalid character")
			}
		}

		val, err := evalArithmetic(trimmed)
		if err != nil {
			return "", err
		}
		return fmt.Sprintf("%v", val), nil
	}

	var evalErr error
	result := re.ReplaceAllStringFunc(text, func(match string) string {
		if evalErr != nil {
			return match
		}
		submatch := re.FindStringSubmatch(match)
		if len(submatch) < 2 {
			return match
		}
		res, err := safeEval(submatch[1])
		if err != nil {
			evalErr = err
			return match
		}
		return res
	})
	if evalErr != nil {
		return "", evalErr
	}
	return result, nil
}

type token struct {
	typ int
	val float64
	op  rune
}

const (
	tokenNum = iota
	tokenOp
	tokenLParen
	tokenRParen
)

func evalArithmetic(expr string) (float64, error) {
	tokens, err := tokenize(expr)
	if err != nil {
		return 0, err
	}
	pos := 0
	var parseExpr func() (float64, error)
	var parseTerm func() (float64, error)
	var parseFactor func() (float64, error)

	parseExpr = func() (float64, error) {
		left, err := parseTerm()
		if err != nil {
			return 0, err
		}
		for pos < len(tokens) && (tokens[pos].op == '+' || tokens[pos].op == '-') {
			op := tokens[pos].op
			pos++
			right, err := parseTerm()
			if err != nil {
				return 0, err
			}
			if op == '+' {
				left += right
			} else {
				left -= right
			}
		}
		return left, nil
	}

	parseTerm = func() (float64, error) {
		left, err := parseFactor()
		if err != nil {
			return 0, err
		}
		for pos < len(tokens) && (tokens[pos].op == '*' || tokens[pos].op == '/') {
			op := tokens[pos].op
			pos++
			right, err := parseFactor()
			if err != nil {
				return 0, err
			}
			if op == '*' {
				left *= right
			} else {
				if right == 0 {
					return 0, fmt.Errorf("division by zero")
				}
				left /= right
			}
		}
		return left, nil
	}

	parseFactor = func() (float64, error) {
		if pos >= len(tokens) {
			return 0, fmt.Errorf("invalid expression")
		}
		tok := tokens[pos]
		if tok.op == '+' {
			pos++
			return parseFactor()
		}
		if tok.op == '-' {
			pos++
			val, err := parseFactor()
			if err != nil {
				return 0, err
			}
			return -val, nil
		}
		if tok.typ == tokenLParen {
			pos++
			val, err := parseExpr()
			if err != nil {
				return 0, err
			}
			if pos >= len(tokens) || tokens[pos].typ != tokenRParen {
				return 0, fmt.Errorf("invalid expression: mismatched parentheses")
			}
			pos++
			return val, nil
		}
		if tok.typ == tokenNum {
			pos++
			return tok.val, nil
		}
		return 0, fmt.Errorf("invalid expression")
	}

	res, err := parseExpr()
	if err != nil {
		return 0, err
	}
	if pos != len(tokens) {
		return 0, fmt.Errorf("invalid expression")
	}
	return res, nil
}

func tokenize(expr string) ([]token, error) {
	var tokens []token
	i := 0
	for i < len(expr) {
		ch := expr[i]
		if ch == ' ' {
			i++
			continue
		}
		if ch == '+' || ch == '-' || ch == '*' || ch == '/' {
			tokens = append(tokens, token{typ: tokenOp, op: rune(ch)})
			i++
		} else if ch == '(' {
			tokens = append(tokens, token{typ: tokenLParen, op: '('})
			i++
		} else if ch == ')' {
			tokens = append(tokens, token{typ: tokenRParen, op: ')'})
			i++
		} else if ch >= '0' && ch <= '9' {
			start := i
			for i < len(expr) && expr[i] >= '0' && expr[i] <= '9' {
				i++
			}
			var val float64
			_, err := fmt.Sscan(expr[start:i], &val)
			if err != nil {
				return nil, fmt.Errorf("invalid number")
			}
			tokens = append(tokens, token{typ: tokenNum, val: val})
		} else {
			return nil, fmt.Errorf("invalid character in expression")
		}
	}
	return tokens, nil
}

func main() {
	passed := true

	assertEqual := func(got, want string) {
		if got != want {
			fmt.Printf("FAIL: got %q, want %q\n", got, want)
			passed = false
		}
	}

	assertError := func(err error) {
		if err == nil {
			fmt.Println("FAIL: expected an error but got nil")
			passed = false
		}
	}

	// Test 1
	res, err := evaluateExpressions("The area is {{5 * 4}} square units.")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "The area is 20 square units.")
	}

	// Test 2
	res, err = evaluateExpressions("There are {{ 3 + 2 }} birds.")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "There are 5 birds.")
	}

	// Test 3
	res, err = evaluateExpressions("Mix {{2+3}} and {{10/2}}.")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "Mix 5 and 5.")
	}

	// Test 4
	res, err = evaluateExpressions("No expressions here.")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "No expressions here.")
	}

	// Test 5: malicious input with semicolon and function call
	_, err = evaluateExpressions("Bad {{ 3 * 4; open('file.txt') }}")
	assertError(err)

	// Test 6: malicious input with letters and semicolon
	_, err = evaluateExpressions("Bad {{ls -l ;2 + 3}}")
	assertError(err)

	// Test 7: division by zero
	_, err = evaluateExpressions("Divide {{3/0}} now")
	if err == nil || !strings.Contains(err.Error(), "division by zero") {
		fmt.Printf("FAIL: expected division by zero error, got %v\n", err)
		passed = false
	}

	if !passed {
		fmt.Println("Validation failed.")
	} else {
		fmt.Println("All tests passed.")
	}
}