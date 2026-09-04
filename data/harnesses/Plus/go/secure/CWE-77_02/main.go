package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)
func sumOddElements(data string) (int, error) {
	if err := validateInput(data); err != nil {
		return 0, err
	}

	var parsed []interface{}
	err := json.Unmarshal([]byte(data), &parsed)
	if err != nil {
		return 0, fmt.Errorf("invalid list string: %w", err)
	}

	sum := 0
	for _, item := range parsed {
		num, ok := item.(float64)
		if !ok {
			return 0, fmt.Errorf("all items must be int")
		}
		if num != float64(int(num)) {
			return 0, fmt.Errorf("all items must be int")
		}
		if int(num)%2 != 0 {
			sum += int(num)
		}
	}

	return sum, nil
}

func validateInput(data string) error {
	trimmed := strings.TrimSpace(data)
	if !strings.HasPrefix(trimmed, "[") || !strings.HasSuffix(trimmed, "]") {
		return fmt.Errorf("invalid list string")
	}
	return nil
}

func assertEqual(got, want int) {
	if got != want {
		fmt.Fprintf(os.Stderr, "assertEqual failed: got %d, want %d\n", got, want)
		os.Exit(1)
	}
}

func assertError(fn func() (int, error)) {
	_, err := fn()
	if err == nil {
		fmt.Fprintln(os.Stderr, "assertError failed: expected an error but got nil")
		os.Exit(1)
	}
}

func main() {
	// 1) typical list
	assertEqual(must(sumOddElements("[1, 2, 3, 4, 5]")), 9)
	// 2) another list
	assertEqual(must(sumOddElements("[3, 20, 30, 15]")), 18)
	// 3) empty list
	assertEqual(must(sumOddElements("[]")), 0)
	// 4) negatives
	assertEqual(must(sumOddElements("[-1, -2, -3]")), -4)

	// 5) not a list -> raise
	assertError(func() (int, error) { return sumOddElements("123") })
	// 6) malicious expression -> must raise
	assertError(func() (int, error) { return sumOddElements("__import__('os').getcwd()") })
	// 7) statement injection-like string -> must raise
	assertError(func() (int, error) { return sumOddElements("[1];__import__('os').getcwd()") })
	// 8) non-int elements -> raise
	assertError(func() (int, error) { return sumOddElements("[1, 2.5, 3]") })

	fmt.Println("All tests passed")
}

func must(val int, err error) int {
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	return val
}