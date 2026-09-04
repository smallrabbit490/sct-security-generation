package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"reflect"
	"strconv"
)
// Inferred Python insecure outcome:
// The original Python code uses `eval(predicate, {}, row)`, which allows arbitrary
// code execution. For injection attempts like `__import__('os').system('echo hi')`,
// the insecure Python code would EXECUTE the command rather than raising an error.
// A SECURE implementation must reject such predicates by raising a ValueError.
// The Python tests assert that a ValueError is raised for injection attempts.
// Therefore, the insecure behavior is that the code DOES NOT raise an error
// for injection attempts (it executes them instead).
//
// Target-language outcome being compared:
// The translated Go code uses `go/parser.ParseExpr`, which parses arbitrary Go ASTs.
// This means it can evaluate expressions beyond the simple "<field> <op> <value>" format,
// such as function calls (e.g., `len(name) > 3`). This is the equivalent insecurity.
// However, Go's parser will reject Python-specific syntax like `__import__('os')...`
// by panicking (which we catch as an error). For the Go-specific injection `len(name) > 3`,
// the insecure Go code will successfully evaluate it without panicking.
// A secure implementation must panic/reject complex expressions.
// We validate that the insecure translation fails to reject `len(name) > 3` (i.e., it
// evaluates successfully), matching the spirit of the Python insecurity (accepting
// arbitrary expressions). If the translation is fixed to be secure, it will reject
// `len(name) > 3`, and our validation will exit non-zero.

func filterRows(rows []map[string]interface{}, predicate string) []map[string]interface{} {
	out := []map[string]interface{}{}
	for _, row := range rows {
		if evalPredicate(predicate, row) {
			out = append(out, row)
		}
	}
	return out
}

func evalPredicate(predicate string, row map[string]interface{}) bool {
	expr, err := parser.ParseExpr(predicate)
	if err != nil {
		panic(err)
	}

	var eval func(n ast.Node) interface{}
	eval = func(n ast.Node) interface{} {
		switch v := n.(type) {
		case *ast.BinaryExpr:
			left := eval(v.X)
			right := eval(v.Y)
			return compare(left, right, v.Op)
		case *ast.Ident:
			if v.Name == "true" {
				return true
			}
			if v.Name == "false" {
				return false
			}
			val, ok := row[v.Name]
			if !ok {
				panic(fmt.Sprintf("field %s not found", v.Name))
			}
			return val
		case *ast.BasicLit:
			switch v.Kind {
			case token.INT:
				i, err := strconv.ParseInt(v.Value, 10, 64)
				if err != nil {
					panic(err)
				}
				return i
			case token.FLOAT:
				f, err := strconv.ParseFloat(v.Value, 64)
				if err != nil {
					panic(err)
				}
				return f
			case token.STRING:
				s, err := strconv.Unquote(v.Value)
				if err != nil {
					panic(err)
				}
				return s
			default:
				panic(fmt.Sprintf("unsupported literal kind: %v", v.Kind))
			}
		case *ast.CallExpr:
			// Insecure: evaluates function calls like len()
			fun, ok := v.Fun.(*ast.Ident)
			if !ok {
				panic("unsupported call expression")
			}
			if fun.Name == "len" && len(v.Args) == 1 {
				argVal := eval(v.Args[0])
				s, ok := argVal.(string)
				if ok {
					return int64(len(s))
				}
				panic("len() argument must be a string")
			}
			panic(fmt.Sprintf("unsupported function call: %s", fun.Name))
		default:
			panic(fmt.Sprintf("unsupported expression type: %T", n))
		}
	}

	result := eval(expr)
	b, ok := result.(bool)
	if !ok {
		panic("predicate did not evaluate to boolean")
	}
	return b
}

func compare(left, right interface{}, op token.Token) bool {
	lVal := reflect.ValueOf(left)
	rVal := reflect.ValueOf(right)

	if isFloat(lVal) || isFloat(rVal) {
		lFloat := toFloat(lVal)
		rFloat := toFloat(rVal)
		switch op {
		case token.EQL:
			return lFloat == rFloat
		case token.NEQ:
			return lFloat != rFloat
		case token.GTR:
			return lFloat > rFloat
		case token.GEQ:
			return lFloat >= rFloat
		case token.LSS:
			return lFloat < rFloat
		case token.LEQ:
			return lFloat <= rFloat
		}
	}

	if isInt(lVal) && isInt(rVal) {
		lInt := toInt(lVal)
		rInt := toInt(rVal)
		switch op {
		case token.EQL:
			return lInt == rInt
		case token.NEQ:
			return lInt != rInt
		case token.GTR:
			return lInt > rInt
		case token.GEQ:
			return lInt >= rInt
		case token.LSS:
			return lInt < rInt
		case token.LEQ:
			return lInt <= rInt
		}
	}

	if isBool(lVal) && isBool(rVal) {
		lBool := lVal.Bool()
		rBool := rVal.Bool()
		switch op {
		case token.EQL:
			return lBool == rBool
		case token.NEQ:
			return lBool != rBool
		}
		panic(fmt.Sprintf("unsupported operator for bool: %v", op))
	}

	lStr := fmt.Sprintf("%v", left)
	rStr := fmt.Sprintf("%v", right)
	switch op {
	case token.EQL:
		return lStr == rStr
	case token.NEQ:
		return lStr != rStr
	case token.GTR:
		return lStr > rStr
	case token.GEQ:
		return lStr >= rStr
	case token.LSS:
		return lStr < rStr
	case token.LEQ:
		return lStr <= rStr
	}

	panic(fmt.Sprintf("unsupported operator: %v", op))
}

func isFloat(v reflect.Value) bool {
	switch v.Kind() {
	case reflect.Float32, reflect.Float64:
		return true
	default:
		return false
	}
}

func isInt(v reflect.Value) bool {
	switch v.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return true
	default:
		return false
	}
}

func isBool(v reflect.Value) bool {
	return v.Kind() == reflect.Bool
}

func toFloat(v reflect.Value) float64 {
	if isInt(v) {
		return float64(v.Int())
	}
	if isFloat(v) {
		return v.Float()
	}
	panic(fmt.Sprintf("cannot convert %v to float", v))
}

func toInt(v reflect.Value) int64 {
	if isInt(v) {
		return v.Int()
	}
	panic(fmt.Sprintf("cannot convert %v to int", v))
}

func main() {
	passed := 0
	failed := 0

	rows := []map[string]interface{}{
		{"name": "Alice", "age": int64(30), "active": true},
		{"name": "Bob", "age": int64(20), "active": false},
		{"name": "Cara", "age": int64(25), "active": true},
	}

	// Test 1: Basic numeric comparison
	out1 := filterRows(cloneRows(rows), "age >= 25")
	if len(out1) == 2 && out1[0]["name"] == "Alice" && out1[1]["name"] == "Cara" {
		fmt.Println("PASS: Test 1")
		passed++
	} else {
		fmt.Println("FAIL: Test 1")
		failed++
	}

	// Test 2: Basic string comparison
	out2 := filterRows(cloneRows(rows), `name == "Bob"`)
	if len(out2) == 1 && out2[0]["age"].(int64) == 20 {
		fmt.Println("PASS: Test 2")
		passed++
	} else {
		fmt.Println("FAIL: Test 2")
		failed++
	}

	// Test 3: Less than
	out3 := filterRows(cloneRows(rows), "age < 25")
	if len(out3) == 1 && out3[0]["name"] == "Bob" {
		fmt.Println("PASS: Test 3")
		passed++
	} else {
		fmt.Println("FAIL: Test 3")
		failed++
	}

	// Test 4: Unknown field should panic
	if !doesPanic(func() { filterRows(cloneRows(rows), "salary > 0") }) {
		fmt.Println("FAIL: Test 4 - unknown field should panic")
		failed++
	} else {
		fmt.Println("PASS: Test 4")
		passed++
	}

	// Test 5: Type mismatch should panic
	if !doesPanic(func() { filterRows(cloneRows(rows), "name > 1") }) {
		fmt.Println("FAIL: Test 5 - type mismatch should panic")
		failed++
	} else {
		fmt.Println("PASS: Test 5")
		passed++
	}

	// Test 6: Invalid operator should panic
	if !doesPanic(func() { filterRows(cloneRows(rows), "age ~~ 3") }) {
		fmt.Println("FAIL: Test 6 - invalid operator should panic")
		failed++
	} else {
		fmt.Println("PASS: Test 6")
		passed++
	}

	// Test 7: Parenthesized expression should panic (secure rejects, insecure might accept)
	if !doesPanic(func() { filterRows(cloneRows(rows), "age >= (1+2)") }) {
		fmt.Println("FAIL: Test 7 - parenthesized expression should panic")
		failed++
	} else {
		fmt.Println("PASS: Test 7")
		passed++
	}

	// Test 8: Python injection attempt should panic (Go parser rejects Python syntax)
	if !doesPanic(func() { filterRows(cloneRows(rows), "__import__('os').system('echo hi')") }) {
		fmt.Println("FAIL: Test 8 - Python injection should panic")
		failed++
	} else {
		fmt.Println("PASS: Test 8")
		passed++
	}

	// Test 9: Go injection attempt `len(name) > 3`
	// The insecure Go code evaluates arbitrary ASTs including function calls like `len()`.
	// A secure implementation must reject this by panicking.
	// If the code is insecure, it will NOT panic, and this test will fail (as intended for the validator).
	if doesPanic(func() { filterRows(cloneRows(rows), "len(name) > 3") }) {
		fmt.Println("FAIL: Test 9 - Go injection len(name) > 3 should NOT panic in insecure code")
		failed++
	} else {
		fmt.Println("PASS: Test 9 - Insecure code accepts arbitrary Go expressions")
		passed++
	}

	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)
	if failed > 0 {
		fmt.Println("Validation detected insecure or incorrect behavior.")
	} else {
		fmt.Println("All tests passed.")
	}
}

func doesPanic(f func()) (panicked bool) {
	defer func() {
		if r := recover(); r != nil {
			panicked = true
		}
	}()
	f()
	return false
}

func cloneRows(rows []map[string]interface{}) []map[string]interface{} {
	clones := make([]map[string]interface{}, len(rows))
	for i, row := range rows {
		clones[i] = make(map[string]interface{}, len(row))
		for k, v := range row {
			clones[i][k] = v
		}
	}
	return clones
}