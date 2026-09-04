package main

import (
	"fmt"
	"reflect"
	"strings"
)
func parseCSVLine(line interface{}) []string {
	if _, ok := line.(string); !ok {
		panic("line must be a string")
	}

	s := line.(string)
	if strings.Contains(s, "\n") || strings.Contains(s, "\r") {
		panic("line must not contain newlines")
	}

	var fields []string
	var buf strings.Builder
	inQuotes := false
	i := 0
	n := len(s)

	for i < n {
		ch := s[i]
		if inQuotes {
			if ch == '"' {
				if i+1 < n && s[i+1] == '"' {
					buf.WriteByte('"')
					i += 2
					continue
				}
				inQuotes = false
				i++
				continue
			} else {
				buf.WriteByte(ch)
				i++
				continue
			}
		} else {
			if ch == '"' {
				inQuotes = true
				i++
				continue
			}
			if ch == ',' {
				fields = append(fields, buf.String())
				buf.Reset()
				i++
				continue
			}
			buf.WriteByte(ch)
			i++
		}
	}

	if inQuotes {
		panic("unterminated quoted field")
	}

	fields = append(fields, buf.String())
	return fields
}

func assertPanic(f func()) {
	defer func() {
		if r := recover(); r == nil {
			fmt.Println("FAIL: expected panic but none was raised")
			panic("test failed")
		}
	}()
	f()
}

func main() {
	passed := true

	check := func(condition bool, msg string) {
		if !condition {
			fmt.Println("FAIL:", msg)
			passed = false
		}
	}

	check(
		reflect.DeepEqual(parseCSVLine("a,b,c"), []string{"a", "b", "c"}),
		`parseCSVLine("a,b,c") == ["a", "b", "c"]`,
	)
	check(
		reflect.DeepEqual(parseCSVLine(`"a,b",c`), []string{"a,b", "c"}),
		`parseCSVLine("\"a,b\",c") == ["a,b", "c"]`,
	)
	check(
		reflect.DeepEqual(parseCSVLine(`x,"he said ""hi""",y`), []string{"x", `he said "hi"`, "y"}),
		`parseCSVLine("x,\"he said \"\"hi\"\"\",y") == ["x", "he said \"hi\"", "y"]`,
	)
	check(
		reflect.DeepEqual(parseCSVLine(""), []string{""}),
		`parseCSVLine("") == [""]`,
	)

	// Test panic for unterminated quoted field
	func() {
		didPanic := false
		func() {
			defer func() {
				if r := recover(); r != nil {
					didPanic = true
				}
			}()
			parseCSVLine(`"a,b`)
		}()
		check(didPanic, `parseCSVLine("\"a,b") should panic`)
	}()

	// Test panic for newline in line
	func() {
		didPanic := false
		func() {
			defer func() {
				if r := recover(); r != nil {
					didPanic = true
				}
			}()
			parseCSVLine("a\nb,c")
		}()
		check(didPanic, `parseCSVLine("a\\nb,c") should panic`)
	}()

	// Test panic for nil input
	func() {
		didPanic := false
		func() {
			defer func() {
				if r := recover(); r != nil {
					didPanic = true
				}
			}()
			parseCSVLine(nil)
		}()
		check(didPanic, `parseCSVLine(nil) should panic`)
	}()

	// Test panic for integer input
	func() {
		didPanic := false
		func() {
			defer func() {
				if r := recover(); r != nil {
					didPanic = true
				}
			}()
			parseCSVLine(123)
		}()
		check(didPanic, `parseCSVLine(123) should panic`)
	}()

	if !passed {
		panic("validation failed")
	}
}