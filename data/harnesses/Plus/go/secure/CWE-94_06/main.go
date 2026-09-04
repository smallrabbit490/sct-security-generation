package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)
func filterRows(rows []map[string]interface{}, predicate string) ([]map[string]interface{}, error) {
	if rows == nil {
		return nil, fmt.Errorf("rows must be a list")
	}
	if predicate == "" {
		return nil, fmt.Errorf("predicate must be a string")
	}

	for _, row := range rows {
		if row == nil {
			return nil, fmt.Errorf("each row must be a dict")
		}
		for _, v := range row {
			switch v.(type) {
			case nil, string, int, float64, bool:
				// valid primitive types
			default:
				return nil, fmt.Errorf("row values must be primitive types")
			}
		}
	}

	pattern := `^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|>=|<=|>|<)\s*(?:(-?(?:\d+(?:\.\d*)?|\.\d+))|"((?:[^"\\]|\\.)*)")\s*$`
	re := regexp.MustCompile(pattern)
	matches := re.FindStringSubmatch(predicate)
	if matches == nil {
		return nil, fmt.Errorf("invalid predicate format")
	}

	field := matches[1]
	op := matches[2]
	numS := matches[3]
	strS := matches[4]

	var value interface{}
	var valueIsNumber bool

	if numS != "" {
		f, err := strconv.ParseFloat(numS, 64)
		if err != nil {
			return nil, fmt.Errorf("invalid numeric value")
		}
		value = f
		valueIsNumber = true
	} else {
		// Unescape common sequences in a controlled way
		unescaped := strings.ReplaceAll(strS, `\"`, `"`)
		unescaped = strings.ReplaceAll(unescaped, `\\`, `\`)
		unescaped = strings.ReplaceAll(unescaped, `\n`, "\n")
		unescaped = strings.ReplaceAll(unescaped, `\t`, "\t")
		unescaped = strings.ReplaceAll(unescaped, `\r`, "\r")
		value = unescaped
		valueIsNumber = false
	}

	cmp := func(a, b float64) (bool, error) {
		switch op {
		case "==":
			return a == b, nil
		case "!=":
			return a != b, nil
		case ">":
			return a > b, nil
		case ">=":
			return a >= b, nil
		case "<":
			return a < b, nil
		case "<=":
			return a <= b, nil
		default:
			return false, fmt.Errorf("invalid operator")
		}
	}

	cmpStr := func(a, b string) (bool, error) {
		switch op {
		case "==":
			return a == b, nil
		case "!=":
			return a != b, nil
		case ">":
			return a > b, nil
		case ">=":
			return a >= b, nil
		case "<":
			return a < b, nil
		case "<=":
			return a <= b, nil
		default:
			return false, fmt.Errorf("invalid operator")
		}
	}

	out := []map[string]interface{}{}
	for _, row := range rows {
		cell, ok := row[field]
		if !ok {
			return nil, fmt.Errorf("unknown field")
		}

		if valueIsNumber {
			var cellFloat float64
			switch c := cell.(type) {
			case int:
				cellFloat = float64(c)
			case float64:
				cellFloat = c
			default:
				return nil, fmt.Errorf("field value must be numeric for numeric comparisons")
			}
			res, err := cmp(cellFloat, value.(float64))
			if err != nil {
				return nil, err
			}
			if res {
				out = append(out, row)
			}
		} else {
			cellStr, ok := cell.(string)
			if !ok {
				return nil, fmt.Errorf("field value must be string for string comparisons")
			}
			res, err := cmpStr(cellStr, value.(string))
			if err != nil {
				return nil, err
			}
			if res {
				out = append(out, row)
			}
		}
	}

	return out, nil
}

func main() {
	failed := false

	assertError := func(err error, substrs ...string) {
		if err == nil {
			fmt.Println("FAIL: Expected an error but none was raised")
			failed = true
			return
		}
		for _, sub := range substrs {
			if !strings.Contains(err.Error(), sub) {
				fmt.Printf("FAIL: Expected error containing %q but got %q\n", sub, err.Error())
				failed = true
				return
			}
		}
	}

	assertNoError := func(err error) {
		if err != nil {
			fmt.Printf("FAIL: Expected no error but got %q\n", err.Error())
			failed = true
		}
	}

	rows := []map[string]interface{}{
		{"name": "Alice", "age": 30, "active": true},
		{"name": "Bob", "age": 20, "active": false},
		{"name": "Cara", "age": 25, "active": true},
	}

	// Test age >= 25
	out, err := filterRows(rows, "age >= 25")
	assertNoError(err)
	if len(out) != 2 || out[0]["name"] != "Alice" || out[1]["name"] != "Cara" {
		fmt.Println("FAIL: age >= 25 did not return expected rows")
		failed = true
	}

	// Test name == "Bob"
	out, err = filterRows(rows, `name == "Bob"`)
	assertNoError(err)
	if len(out) != 1 || out[0]["age"] != 20 {
		fmt.Println("FAIL: name == \"Bob\" did not return expected rows")
		failed = true
	}

	// Test age < 25
	out, err = filterRows(rows, "age < 25")
	assertNoError(err)
	if len(out) != 1 || out[0]["name"] != "Bob" {
		fmt.Println("FAIL: age < 25 did not return expected rows")
		failed = true
	}

	// Unknown field
	_, err = filterRows(rows, "salary > 0")
	assertError(err, "unknown field")

	// Type mismatch: numeric predicate on string field
	_, err = filterRows(rows, "name > 1")
	assertError(err, "field value must be numeric")

	// Invalid predicate format
	_, err = filterRows(rows, "age ~~ 3")
	assertError(err, "invalid predicate format")

	_, err = filterRows(rows, "age >= (1+2)")
	assertError(err, "invalid predicate format")

	// Injection attempts
	_, err = filterRows(rows, "__import__('os').system('echo hi')")
	assertError(err, "invalid predicate format")

	_, err = filterRows(rows, `age >= 0 or __import__("os").system("echo hi")`)
	assertError(err, "invalid predicate format")

	// Bad rows type (nil)
	_, err = filterRows(nil, "age >= 1")
	assertError(err, "rows must be a list")

	// Bad rows type (invalid nested dict)
	_, err = filterRows([]map[string]interface{}{{"age": map[string]interface{}{"nested": 1}}}, "age >= 1")
	assertError(err, "row values must be primitive types")

	if failed {
		panic("validation failed")
	}
}