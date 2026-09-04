package main

import (
	"errors"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"math"
	"os"
	"strconv"
)

func evalInput(inputStr interface{}) (interface{}, error) {
	// Check type
	if _, ok := inputStr.(string); !ok {
		return nil, errors.New("TypeError")
	}

	str := inputStr.(string)

	// Check length
	if len(str) > 200 {
		return nil, errors.New("ValueError")
	}

	// Parse the expression
	node, err := parser.ParseExpr(str)
	if err != nil {
		return nil, errors.New("ValueError")
	}

	// Validate the AST
	v := &validator{}
	ast.Walk(v, node)
	if v.err != nil {
		return nil, v.err
	}

	// Evaluate the expression
	result, err := eval(node)
	if err != nil {
		return nil, errors.New("ValueError")
	}

	return result, nil
}

type validator struct {
	err error
}

func (v *validator) Visit(n ast.Node) ast.Visitor {
	if v.err != nil {
		return nil
	}

	switch node := n.(type) {
	case *ast.Ident:
		v.err = errors.New("ValueError")
		return nil
	case *ast.BasicLit:
		if node.Kind != token.INT && node.Kind != token.FLOAT {
			v.err = errors.New("ValueError")
			return nil
		}
	case *ast.BinaryExpr:
		switch node.Op {
		case token.ADD, token.SUB, token.MUL, token.QUO, token.REM:
		default:
			v.err = errors.New("ValueError")
			return nil
		}
	case *ast.UnaryExpr:
		switch node.Op {
		case token.ADD, token.SUB:
		default:
			v.err = errors.New("ValueError")
			return nil
		}
	case *ast.ParenExpr:
		// Always allowed
	case *ast.CallExpr:
		v.err = errors.New("ValueError")
		return nil
	}

	return v
}

func eval(expr ast.Expr) (interface{}, error) {
	switch e := expr.(type) {
	case *ast.BasicLit:
		switch e.Kind {
		case token.INT:
			return strconv.ParseInt(e.Value, 10, 64)
		case token.FLOAT:
			return strconv.ParseFloat(e.Value, 64)
		default:
			return nil, errors.New("unsupported literal type")
		}
	case *ast.BinaryExpr:
		left, err := eval(e.X)
		if err != nil {
			return nil, err
		}
		right, err := eval(e.Y)
		if err != nil {
			return nil, err
		}

		switch e.Op {
		case token.ADD:
			return add(left, right)
		case token.SUB:
			return sub(left, right)
		case token.MUL:
			return mul(left, right)
		case token.QUO:
			return div(left, right)
		case token.REM:
			return mod(left, right)
		default:
			return nil, fmt.Errorf("unsupported operator: %s", e.Op)
		}
	case *ast.UnaryExpr:
		operand, err := eval(e.X)
		if err != nil {
			return nil, err
		}

		switch e.Op {
		case token.ADD:
			return operand, nil
		case token.SUB:
			return neg(operand)
		default:
			return nil, fmt.Errorf("unsupported unary operator: %s", e.Op)
		}
	case *ast.ParenExpr:
		return eval(e.X)
	default:
		return nil, errors.New("unsupported expression type")
	}
}

func add(a, b interface{}) (interface{}, error) {
	switch x := a.(type) {
	case int64:
		switch y := b.(type) {
		case int64:
			return x + y, nil
		case float64:
			return float64(x) + y, nil
		}
	case float64:
		switch y := b.(type) {
		case int64:
			return x + float64(y), nil
		case float64:
			return x + y, nil
		}
	}
	return nil, errors.New("type mismatch in addition")
}

func sub(a, b interface{}) (interface{}, error) {
	switch x := a.(type) {
	case int64:
		switch y := b.(type) {
		case int64:
			return x - y, nil
		case float64:
			return float64(x) - y, nil
		}
	case float64:
		switch y := b.(type) {
		case int64:
			return x - float64(y), nil
		case float64:
			return x - y, nil
		}
	}
	return nil, errors.New("type mismatch in subtraction")
}

func mul(a, b interface{}) (interface{}, error) {
	switch x := a.(type) {
	case int64:
		switch y := b.(type) {
		case int64:
			return x * y, nil
		case float64:
			return float64(x) * y, nil
		}
	case float64:
		switch y := b.(type) {
		case int64:
			return x * float64(y), nil
		case float64:
			return x * y, nil
		}
	}
	return nil, errors.New("type mismatch in multiplication")
}

func div(a, b interface{}) (interface{}, error) {
	switch x := a.(type) {
	case int64:
		switch y := b.(type) {
		case int64:
			if y == 0 {
				return nil, errors.New("division by zero")
			}
			return float64(x) / float64(y), nil
		case float64:
			if y == 0 {
				return nil, errors.New("division by zero")
			}
			return float64(x) / y, nil
		}
	case float64:
		switch y := b.(type) {
		case int64:
			if y == 0 {
				return nil, errors.New("division by zero")
			}
			return x / float64(y), nil
		case float64:
			if y == 0 {
				return nil, errors.New("division by zero")
			}
			return x / y, nil
		}
	}
	return nil, errors.New("type mismatch in division")
}

func mod(a, b interface{}) (interface{}, error) {
	switch x := a.(type) {
	case int64:
		switch y := b.(type) {
		case int64:
			if y == 0 {
				return nil, errors.New("division by zero")
			}
			return x % y, nil
		case float64:
			return nil, errors.New("modulo with float not supported")
		}
	case float64:
		return nil, errors.New("modulo with float not supported")
	}
	return nil, errors.New("type mismatch in modulo")
}

func pow(a, b interface{}) (interface{}, error) {
	switch x := a.(type) {
	case int64:
		switch y := b.(type) {
		case int64:
			return math.Pow(float64(x), float64(y)), nil
		case float64:
			return math.Pow(float64(x), y), nil
		}
	case float64:
		switch y := b.(type) {
		case int64:
			return math.Pow(x, float64(y)), nil
		case float64:
			return math.Pow(x, y), nil
		}
	}
	return nil, errors.New("type mismatch in power")
}

func neg(a interface{}) (interface{}, error) {
	switch x := a.(type) {
	case int64:
		return -x, nil
	case float64:
		return -x, nil
	}
	return nil, errors.New("type mismatch in negation")
}

func main() {
	passed := true

	// Helper to compare interface{} values (int64 vs float64)
	eq := func(a, b interface{}) bool {
		switch va := a.(type) {
		case int64:
			switch vb := b.(type) {
			case int64:
				return va == vb
			case float64:
				return float64(va) == vb
			}
		case float64:
			switch vb := b.(type) {
			case int64:
				return va == float64(vb)
			case float64:
				return va == vb
			}
		}
		return false
	}

	// 1) simple arithmetic
	res, err := evalInput("1+2*3")
	if err != nil || !eq(res, int64(7)) {
		fmt.Println("Test 1 failed: simple arithmetic")
		passed = false
	}

	// 2) parentheses
	res, err = evalInput("(1+2)*3")
	if err != nil || !eq(res, int64(9)) {
		fmt.Println("Test 2 failed: parentheses")
		passed = false
	}

	// 3) unary
	res, err = evalInput("-5+2")
	if err != nil || !eq(res, int64(-3)) {
		fmt.Println("Test 3 failed: unary")
		passed = false
	}

	// 4) reject code execution attempt
	_, err = evalInput("__import__('os').system('id')")
	if err == nil {
		fmt.Println("Test 4 failed: reject code execution attempt")
		passed = false
	}

	// 5) reject attribute access
	_, err = evalInput("(1).__class__")
	if err == nil {
		fmt.Println("Test 5 failed: reject attribute access")
		passed = false
	}

	// 6) reject non-str
	_, err = evalInput(123)
	if err == nil {
		fmt.Println("Test 6 failed: reject non-str")
		passed = false
	}

	// 7) extra arg rejected
	// Note: Go is statically typed, so we cannot pass extra arguments to evalInput.
	// The function signature is fixed. This test is implicitly handled by the compiler.
	// We simulate the check by ensuring the function behaves correctly with valid args.
	// If the user tried to call evalInput with 2 args, it wouldn't compile.
	// So we just mark this as passed for the sake of the runtime check.
	_ = "Test 7 passed (compile time check)"

	if !passed {
		os.Exit(1)
	}
}