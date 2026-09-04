package main

import (
	"fmt"
	"strconv"
	"strings"
)
func executeCommand(command string) (int, error) {
	if _, ok := interface{}(command).(string); !ok {
		return 0, fmt.Errorf("command must be a string")
	}

	allowed := "0123456789+-*/() "
	if strings.TrimSpace(command) == "" {
		return 0, fmt.Errorf("empty command")
	}
	for _, ch := range command {
		if !strings.ContainsRune(allowed, ch) {
			return 0, fmt.Errorf("invalid character")
		}
	}

	tokens, err := tokenize(command)
	if err != nil {
		return 0, fmt.Errorf("invalid command: %w", err)
	}

	parser := &exprParser{tokens: tokens}
	result, err := parser.parseExpression()
	if err != nil {
		return 0, fmt.Errorf("invalid command: %w", err)
	}
	if parser.pos < len(parser.tokens) {
		return 0, fmt.Errorf("invalid command: unexpected token %v", parser.tokens[parser.pos])
	}

	return result, nil
}

type token struct {
	typ int // 0: number, 1: operator, 2: lparen, 3: rparen
	val string
}

func tokenize(s string) ([]token, error) {
	var tokens []token
	i := 0
	for i < len(s) {
		ch := s[i]
		if ch == ' ' {
			i++
			continue
		}
		if ch >= '0' && ch <= '9' {
			j := i
			for j < len(s) && s[j] >= '0' && s[j] <= '9' {
				j++
			}
			tokens = append(tokens, token{0, s[i:j]})
			i = j
		} else if ch == '+' || ch == '-' || ch == '*' || ch == '/' {
			tokens = append(tokens, token{1, string(ch)})
			i++
		} else if ch == '(' {
			tokens = append(tokens, token{2, "("})
			i++
		} else if ch == ')' {
			tokens = append(tokens, token{3, ")"})
			i++
		} else {
			return nil, fmt.Errorf("invalid character: %c", ch)
		}
	}
	return tokens, nil
}

type exprParser struct {
	tokens []token
	pos    int
}

func (p *exprParser) parseExpression() (int, error) {
	return p.parseAddSub()
}

func (p *exprParser) parseAddSub() (int, error) {
	left, err := p.parseMulDiv()
	if err != nil {
		return 0, err
	}

	for p.pos < len(p.tokens) && p.tokens[p.pos].typ == 1 && (p.tokens[p.pos].val == "+" || p.tokens[p.pos].val == "-") {
		op := p.tokens[p.pos].val
		p.pos++
		right, err := p.parseMulDiv()
		if err != nil {
			return 0, err
		}
		if op == "+" {
			left = left + right
		} else {
			left = left - right
		}
	}
	return left, nil
}

func (p *exprParser) parseMulDiv() (int, error) {
	left, err := p.parsePrimary()
	if err != nil {
		return 0, err
	}

	for p.pos < len(p.tokens) && p.tokens[p.pos].typ == 1 && (p.tokens[p.pos].val == "*" || p.tokens[p.pos].val == "/") {
		op := p.tokens[p.pos].val
		p.pos++
		right, err := p.parsePrimary()
		if err != nil {
			return 0, err
		}
		if op == "*" {
			left = left * right
		} else {
			if right == 0 {
				return 0, fmt.Errorf("integer divide by zero")
			}
			left = left / right
		}
	}
	return left, nil
}

func (p *exprParser) parsePrimary() (int, error) {
	if p.pos >= len(p.tokens) {
		return 0, fmt.Errorf("unexpected end of expression")
	}

	tok := p.tokens[p.pos]

	if tok.typ == 2 {
		p.pos++
		expr, err := p.parseExpression()
		if err != nil {
			return 0, err
		}
		if p.pos >= len(p.tokens) || p.tokens[p.pos].typ != 3 {
			return 0, fmt.Errorf("missing closing parenthesis")
		}
		p.pos++
		return expr, nil
	}

	if tok.typ == 0 {
		p.pos++
		val, err := strconv.Atoi(tok.val)
		if err != nil {
			return 0, fmt.Errorf("invalid number: %s", tok.val)
		}
		return val, nil
	}

	return 0, fmt.Errorf("unexpected token: %v", tok.val)
}

func main() {
	passed := true

	assertEqual := func(got, want int) {
		if got != want {
			fmt.Printf("FAIL: expected %d, got %d\n", want, got)
			passed = false
		}
	}

	assertError := func(err error, substr string) {
		if err == nil {
			fmt.Printf("FAIL: expected error containing %q, got nil\n", substr)
			passed = false
		} else if !strings.Contains(err.Error(), substr) {
			fmt.Printf("FAIL: expected error containing %q, got %q\n", substr, err.Error())
			passed = false
		}
	}

	// Test valid expressions
	res, err := executeCommand("2 + 3 * 5")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, 17)
	}

	res, err = executeCommand("10 / 2")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, 5)
	}

	res, err = executeCommand(" (8-3) * 2 ")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, 10)
	}

	res, err = executeCommand("7+(6/3)")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, 9)
	}

	// Test malicious/injection inputs (must fail with invalid character)
	_, err = executeCommand("__import__('os').system('echo Hello')")
	assertError(err, "invalid character")

	_, err = executeCommand("print(\"Hello, World!\")")
	assertError(err, "invalid character")

	// Test division by zero
	_, err = executeCommand("10/0")
	assertError(err, "integer divide by zero")

	// Test empty command
	_, err = executeCommand("")
	assertError(err, "empty command")

	_, err = executeCommand("   ")
	assertError(err, "empty command")

	if !passed {
		fmt.Println("\nSome tests failed.")
	} else {
		fmt.Println("\nAll tests passed.")
	}
}