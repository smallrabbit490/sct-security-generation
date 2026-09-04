package main

import (
	"fmt"
	"math"
	"regexp"
	"strconv"
)
func applyTransform(record map[string]float64, transform string) (map[string]float64, error) {
	if record == nil {
		return nil, fmt.Errorf("record must be a dict")
	}
	if transform == "" {
		return nil, fmt.Errorf("transform must be a string")
	}

	pattern := `^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\+=|-=|\*=|/=)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$`
	re := regexp.MustCompile(pattern)
	matches := re.FindStringSubmatch(transform)
	if matches == nil {
		return nil, fmt.Errorf("invalid transform format")
	}

	field := matches[1]
	op := matches[2]
	numS := matches[3]

	cur, ok := record[field]
	if !ok {
		return nil, fmt.Errorf("unknown field")
	}

	num, err := strconv.ParseFloat(numS, 64)
	if err != nil {
		return nil, fmt.Errorf("invalid number")
	}

	switch op {
	case "+=":
		record[field] = cur + num
	case "-=":
		record[field] = cur - num
	case "*=":
		record[field] = cur * num
	case "/=":
		if num == 0 {
			return nil, fmt.Errorf("division by zero")
		}
		record[field] = cur / num
	default:
		return nil, fmt.Errorf("invalid operator")
	}

	return record, nil
}

func main() {
	failed := false

	assertFloat64 := func(got, expected float64, msg string) {
		if math.Abs(got-expected) > 1e-9 {
			fmt.Printf("FAIL: %s: got %v, expected %v\n", msg, got, expected)
			failed = true
		}
	}

	assertError := func(err error, msg string) {
		if err == nil {
			fmt.Printf("FAIL: %s: expected an error but none was raised\n", msg)
			failed = true
		}
	}

	// Test 1: count += 5
	r1 := map[string]float64{"count": 10, "rate": 2.5}
	out1, err1 := applyTransform(r1, "count += 5")
	if err1 != nil {
		fmt.Printf("FAIL: Test 1 unexpected error: %v\n", err1)
		failed = true
	} else {
		assertFloat64(out1["count"], 15.0, "Test 1 count")
		assertFloat64(out1["rate"], 2.5, "Test 1 rate")
	}

	// Test 2: rate *= 2
	r2 := map[string]float64{"count": 10, "rate": 2.5}
	out2, err2 := applyTransform(r2, "rate *= 2")
	if err2 != nil {
		fmt.Printf("FAIL: Test 2 unexpected error: %v\n", err2)
		failed = true
	} else {
		assertFloat64(out2["rate"], 5.0, "Test 2 rate")
		assertFloat64(out2["count"], 10.0, "Test 2 count")
	}

	// Test 3: x -= -2
	r3 := map[string]float64{"x": -3}
	out3, err3 := applyTransform(r3, "x -= -2")
	if err3 != nil {
		fmt.Printf("FAIL: Test 3 unexpected error: %v\n", err3)
		failed = true
	} else {
		assertFloat64(out3["x"], -1.0, "Test 3 x")
	}

	// Test 4: x /= 3
	r4 := map[string]float64{"x": 9}
	out4, err4 := applyTransform(r4, "x /= 3")
	if err4 != nil {
		fmt.Printf("FAIL: Test 4 unexpected error: %v\n", err4)
		failed = true
	} else {
		assertFloat64(out4["x"], 3.0, "Test 4 x")
	}

	// Test 5: injection attempt 1
	_, err5 := applyTransform(map[string]float64{"x": 1}, "__import__('os').system('echo hi')")
	assertError(err5, "Test 5 injection attempt")

	// Test 6: injection attempt 2
	_, err6 := applyTransform(map[string]float64{"x": 1}, "x += 1; x = 999")
	assertError(err6, "Test 6 injection attempt")

	// Test 7: invalid field
	_, err7 := applyTransform(map[string]float64{"x": 1}, "y += 1")
	assertError(err7, "Test 7 unknown field")

	// Test 8: division by zero
	_, err8 := applyTransform(map[string]float64{"x": 1}, "x /= 0")
	assertError(err8, "Test 8 division by zero")

	if failed {
		fmt.Println("VALIDATION FAILED")
	} else {
		fmt.Println("ALL TESTS PASSED")
	}

	if failed {
		panic("validation failed")
	}
}