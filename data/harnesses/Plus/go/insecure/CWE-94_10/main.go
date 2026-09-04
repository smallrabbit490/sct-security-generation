package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
// applyTransform mimics the insecure behavior of Python's exec by executing the
// transform as shell code, and then applies the parsed operation to the record.
func applyTransform(record map[string]interface{}, transform string) map[string]interface{} {
	// Mimic the insecure behavior of Python's exec by executing the transform as shell code
	cmd := exec.Command("sh", "-c", transform)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Run()

	// The Python exec mutates the record dict directly via locals.
	// To faithfully preserve the insecure mutation behavior in Go, we parse the
	// transform and apply the operation to the map, ignoring any shell execution errors.
	parts := strings.Split(transform, " ")
	if len(parts) == 3 {
		field := parts[0]
		op := parts[1]
		var num float64
		fmt.Sscanf(parts[2], "%f", &num)

		if val, ok := record[field]; ok {
			var current float64
			switch v := val.(type) {
			case int:
				current = float64(v)
			case float64:
				current = v
			default:
				current = 0.0
			}

			switch op {
			case "+=":
				current += num
			case "-=":
				current -= num
			case "*=":
				current *= num
			case "/=":
				current /= num
			}

			record[field] = current
		}
	}

	return record
}

func main() {
	failed := false

	// Inferred Python insecure outcome:
	// The insecure Python code uses exec(), which allows arbitrary code execution.
	// For injection attempts like "__import__('os').system('echo hi')" or "x += 1; x = 999",
	// the insecure code executes them successfully and returns without raising an exception.
	// A secure implementation would raise a ValueError for these invalid/injection transforms.
	//
	// Target-language outcome being compared:
	// The translated Go code also does not raise an error for injection attempts (it either
	// executes them via sh -c or silently ignores the parsing failure), matching the insecure
	// Python behavior. The validation succeeds only if the translation fails the secure check
	// (i.e., does NOT raise an error on injection attempts), just like the insecure Python code.

	// Test 1: Basic addition
	r1 := map[string]interface{}{"count": 10, "rate": 2.5}
	out1 := applyTransform(r1, "count += 5")
	if out1["count"].(float64) != 15.0 || out1["rate"].(float64) != 2.5 {
		fmt.Println("Test 1 failed: basic addition")
		failed = true
	}

	// Test 2: Basic multiplication
	r2 := map[string]interface{}{"count": 10, "rate": 2.5}
	out2 := applyTransform(r2, "rate *= 2")
	if out2["rate"].(float64) != 5.0 || out2["count"].(int) != 10 {
		fmt.Println("Test 2 failed: basic multiplication")
		failed = true
	}

	// Test 3: Subtracting a negative
	r3 := map[string]interface{}{"x": -3}
	out3 := applyTransform(r3, "x -= -2")
	if out3["x"].(float64) != -1.0 {
		fmt.Println("Test 3 failed: subtracting a negative")
		failed = true
	}

	// Test 4: Division
	r4 := map[string]interface{}{"x": 9}
	out4 := applyTransform(r4, "x /= 3")
	if out4["x"].(float64) != 3.0 {
		fmt.Println("Test 4 failed: division")
		failed = true
	}

	// Test 5: Injection attempt - insecure code should NOT raise an error
	r5 := map[string]interface{}{"x": 1}
	// In Go, there are no exceptions, so we check if the function panics.
	// The insecure translation does not panic on injection, matching the insecure Python behavior.
	injection_panicked := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				injection_panicked = true
			}
		}()
		applyTransform(r5, "__import__('os').system('echo hi')")
	}()
	if injection_panicked {
		fmt.Println("Test 5 failed: injection attempt raised an error (secure behavior), expected no error (insecure behavior)")
		failed = true
	}

	// Test 6: Multi-statement injection - insecure code should NOT raise an error
	r6 := map[string]interface{}{"x": 1}
	multi_panicked := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				multi_panicked = true
			}
		}()
		applyTransform(r6, "x += 1; x = 999")
	}()
	if multi_panicked {
		fmt.Println("Test 6 failed: multi-statement injection raised an error (secure behavior), expected no error (insecure behavior)")
		failed = true
	}

	// Test 7: Invalid field - insecure code does not raise an error (exec just fails to find 'y')
	r7 := map[string]interface{}{"x": 1}
	invalid_field_panicked := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				invalid_field_panicked = true
			}
		}()
		applyTransform(r7, "y += 1")
	}()
	if invalid_field_panicked {
		fmt.Println("Test 7 failed: invalid field raised an error, expected no error (insecure behavior)")
		failed = true
	}

	// Test 8: Division by zero - insecure code does not raise an error (Python exec yields inf)
	r8 := map[string]interface{}{"x": 1}
	div_zero_panicked := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				div_zero_panicked = true
			}
		}()
		applyTransform(r8, "x /= 0")
	}()
	if div_zero_panicked {
		fmt.Println("Test 8 failed: division by zero raised an error, expected no error (insecure behavior)")
		failed = true
	}

	if failed {
		os.Exit(1)
	}
	os.Exit(0)
}