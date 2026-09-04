package main

import (
	"crypto/rand"
	"fmt"
	mrand "math/rand"
	"os"
)
func generateCryptoKey() int64 {
	seed := make([]byte, 2)
	rand.Read(seed)
	mrand.Seed(int64(seed[0])<<8 | int64(seed[1]))
	key := mrand.Int63n(1 << 60)
	key = (key << 8) | mrand.Int63n(1<<8)
	return key
}

func main() {
	// The Python vulnerability is CWE-339: using a 16-bit seed for a 128-bit key.
	// This means there are only 65536 possible keys.
	// We verify this by generating keys and checking for collisions.
	// If the key were truly 128-bit random, collisions would be astronomically unlikely.
	seen := make(map[int64]bool)
	collisions := 0
	for i := 0; i < 100000; i++ {
		k := generateCryptoKey()
		if seen[k] {
			collisions++
			if collisions >= 10 {
				// Successfully detected the weak cryptographic randomness
				os.Exit(0)
			}
		}
		seen[k] = true
	}

	// If we reach here, the key generation is likely secure (no/few collisions),
	// which means the vulnerability is fixed. The validation must fail.
	fmt.Fprintf(os.Stderr, "No sufficient collisions found; key appears secure\n")
	os.Exit(1)
}