package main

import (
	"crypto/rand"
	"errors"
	"fmt"
	"math/big"
	"os"
)

// generateRandomString returns an unpredictable random string that has only ASCII letters with a fixed size equals to length.
func generateRandomString(length int) (string, error) {
	if length <= 0 || length > 4096 {
		return "", errors.New("invalid length")
	}

	const alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
	alphabetLen := big.NewInt(int64(len(alphabet)))

	result := make([]byte, length)
	for i := 0; i < length; i++ {
		n, err := rand.Int(rand.Reader, alphabetLen)
		if err != nil {
			return "", err
		}
		result[i] = alphabet[n.Int64()]
	}

	return string(result), nil
}

func main() {
	// Helper to check if a function panics or returns an error
	assertRaises := func(f func() error, shouldFail bool) {
		err := f()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected an error but got none")
			os.Exit(1)
		}
		if !shouldFail && err != nil {
			fmt.Printf("FAIL: Expected success but got error: %v\n", err)
			os.Exit(1)
		}
	}

	// Test 1: Valid length
	s1, err := generateRandomString(32)
	if err != nil {
		fmt.Printf("FAIL: generateRandomString(32) returned error: %v\n", err)
		os.Exit(1)
	}
	if len(s1) != 32 {
		fmt.Printf("FAIL: Expected length 32, got %d\n", len(s1))
		os.Exit(1)
	}

	// Test 2: Valid length again to check uniqueness
	s2, err := generateRandomString(32)
	if err != nil {
		fmt.Printf("FAIL: generateRandomString(32) returned error: %v\n", err)
		os.Exit(1)
	}
	if len(s2) != 32 {
		fmt.Printf("FAIL: Expected length 32, got %d\n", len(s2))
		os.Exit(1)
	}

	// Test 3: Uniqueness check
	// Note: In Go, we cannot monkeypatch crypto/rand like Python's random.choice.
	// We rely on the cryptographic property that generating two strings sequentially
	// should result in different values with overwhelming probability.
	if s1 == s2 {
		fmt.Println("FAIL: Generated two identical strings in a row")
		os.Exit(1)
	}

	// Test 4: Content check (ASCII letters only)
	const alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
	for _, c := range s1 {
		valid := false
		for _, a := range alphabet {
			if c == a {
				valid = true
				break
			}
		}
		if !valid {
			fmt.Printf("FAIL: String contains invalid character: %c\n", c)
			os.Exit(1)
		}
	}

	// Test 5: Invalid length (0)
	assertRaises(func() error {
		_, err := generateRandomString(0)
		return err
	}, true)

	// Test 6: Invalid length (> 4096)
	assertRaises(func() error {
		_, err := generateRandomString(4097)
		return err
	}, true)

	// Test 7: Negative length
	assertRaises(func() error {
		_, err := generateRandomString(-1)
		return err
	}, true)

	fmt.Println("PASS")
}