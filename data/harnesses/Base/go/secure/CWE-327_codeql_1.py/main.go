package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"errors"
	"fmt"
	"io"
	"os"
)

// Channel defines the interface required for the channel parameter.
type Channel interface {
	Send(data []byte)
}

// send_encrypted encrypts the message using AES-GCM and sends it over the channel.
func send_encrypted(secret_key []byte, channel Channel, message []byte) ([]byte, error) {
	// Validate inputs
	if len(secret_key) == 0 {
		return nil, errors.New("invalid key")
	}
	if len(message) == 0 {
		return nil, errors.New("invalid message")
	}
	if channel == nil {
		return nil, errors.New("invalid channel")
	}

	// Validate key length
	key := secret_key
	if len(key) != 16 && len(key) != 24 && len(key) != 32 {
		return nil, errors.New("invalid key length")
	}

	// Create cipher block
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, errors.New("cipher creation failed")
	}

	// Create GCM mode
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, errors.New("GCM mode creation failed")
	}

	// Generate nonce
	nonce := make([]byte, gcm.NonceSize())
	if _, err = io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, errors.New("nonce generation failed")
	}

	// Encrypt and digest
	ct := gcm.Seal(nil, nonce, message, nil)

	// Combine nonce + tag + ciphertext (tag is included in Seal output)
	out := append(nonce, ct...)

	// Send over channel
	channel.Send(out)

	return out, nil
}

// Mock Channel for testing
type MockChannel struct {
	sent [][]byte
}

func (m *MockChannel) Send(data []byte) {
	m.sent = append(m.sent, data)
}

func main() {
	// Setup test directory
	testDir := "Test/CWE-327_codeql_1"
	if err := os.MkdirAll(testDir, 0755); err != nil {
		fmt.Printf("FATAL: Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	// Test Case 1: Valid encryption
	ch := &MockChannel{}
	key := bytes.Repeat([]byte("K"), 16)
	msg := []byte("hello")

	out1, err := send_encrypted(key, ch, msg)
	if err != nil {
		fmt.Printf("FAIL: First encryption failed: %v\n", err)
		os.Exit(1)
	}

	out2, err := send_encrypted(key, ch, msg)
	if err != nil {
		fmt.Printf("FAIL: Second encryption failed: %v\n", err)
		os.Exit(1)
	}

	// Check return values match sent values
	if len(ch.sent) < 2 {
		fmt.Printf("FAIL: Channel did not receive enough messages\n")
		os.Exit(1)
	}
	if !bytes.Equal(out1, ch.sent[len(ch.sent)-2]) {
		fmt.Printf("FAIL: out1 does not match channel sent value\n")
		os.Exit(1)
	}
	if !bytes.Equal(out2, ch.sent[len(ch.sent)-1]) {
		fmt.Printf("FAIL: out2 does not match channel sent value\n")
		os.Exit(1)
	}

	// Check length (Nonce 12 + Tag 16 + Ciphertext > 28)
	if len(out1) <= 12+16 {
		fmt.Printf("FAIL: Output length too short: %d\n", len(out1))
		os.Exit(1)
	}

	// Check nonces are different
	if bytes.Equal(out1[:12], out2[:12]) {
		fmt.Printf("FAIL: Nonces are identical (not random)\n")
		os.Exit(1)
	}

	// Test Case 2: Invalid key length (ValueError equivalent)
	_, err = send_encrypted(bytes.Repeat([]byte("K"), 15), ch, []byte("hi"))
	if err == nil {
		fmt.Printf("FAIL: Expected error for invalid key length, got nil\n")
		os.Exit(1)
	}

	// Test Case 3: Invalid key type (TypeError equivalent)
	// In Go, we cannot pass a string to []byte, so we simulate the check logic
	// by ensuring the function handles empty slices or nils if type was wrong.
	// However, the Python test passes a string 'K'*16.
	// Since Go is statically typed, we verify the function signature enforces types.
	// We verify the internal logic that rejects empty keys (simulating bad type conversion).
	_, err = send_encrypted([]byte{}, ch, []byte("hi"))
	if err == nil {
		fmt.Printf("FAIL: Expected error for empty key (type check simulation)\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed.")
}