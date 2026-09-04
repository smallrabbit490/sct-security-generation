#include <string>
#include <vector>
#include <stdexcept>
#include <random>
#include <sstream>
#include <iomanip>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <functional>
#include <iostream>
#include <map>

// --- Mock Infrastructure ---

struct FakeCursor {
    bool exists = false;
    std::pair<std::string, std::vector<std::string>> last_insert;
    bool committed = false;

    void execute(const std::string& q, const std::vector<std::string>& params) {
        if (q.find("INSERT") != std::string::npos) {
            last_insert = {q, params};
        }
    }
    bool fetchone() {
        return exists;
    }
};

struct FakeDB {
    FakeCursor cur;
    bool committed = false;

    FakeDB(bool exists = false) : cur{exists} {}

    FakeCursor& cursor() {
        return cur;
    }
    void commit() {
        committed = true;
    }
};

struct Request {
    std::map<std::string, std::string> form;

    Request() = default;
    Request(const std::string& u, const std::string& p) {
        form["username"] = u;
        form["password"] = p;
    }

    std::string get(const std::string& key) const {
        auto it = form.find(key);
        if (it != form.end()) return it->second;
        return "";
    }
};

// Global mocks
Request request;
FakeDB* current_db = nullptr;
std::vector<uint8_t> fixed_salt_vec;

struct MySQLdbMock {
    FakeDB* connect(const std::string&, const std::string&, const std::string&, const std::string&) {
        return current_db;
    }
};

MySQLdbMock MySQLdb_instance;

// --- SHA-256 Implementation ---

std::string sha256(const std::string& input) {
    const uint32_t k[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    };

    std::vector<uint32_t> w(64, 0);
    for (size_t i = 0; i < input.size() / 4; ++i) {
        w[i] = (static_cast<uint8_t>(input[4*i]) << 24) |
               (static_cast<uint8_t>(input[4*i+1]) << 16) |
               (static_cast<uint8_t>(input[4*i+2]) << 8) |
               (static_cast<uint8_t>(input[4*i+3]));
    }

    size_t i = input.size() / 4;
    size_t mod = input.size() % 4;
    w[i] = 0x80 << (24 - mod * 8);
    if (mod) {
        for (size_t j = 0; j < mod; ++j) {
            w[i] |= static_cast<uint8_t>(input[input.size() - mod + j]) << (24 - j * 8);
        }
    }

    if (mod >= 3) {
        ++i;
        w[i] = 0;
    }

    if (i >= 14) {
        for (size_t j = i + 1; j < 16; ++j) w[j] = 0;
    } else {
        for (size_t j = i + 1; j < 14; ++j) w[j] = 0;
    }

    uint64_t len = input.size() * 8;
    w[14] = static_cast<uint32_t>(len >> 32);
    w[15] = static_cast<uint32_t>(len);

    for (size_t j = 16; j < 64; ++j) {
        uint32_t s0 = ((w[j-15] >> 7) | (w[j-15] << 25)) ^ ((w[j-15] >> 18) | (w[j-15] << 14)) ^ (w[j-15] >> 3);
        uint32_t s1 = ((w[j-2] >> 17) | (w[j-2] << 15)) ^ ((w[j-2] >> 19) | (w[j-2] << 13)) ^ (w[j-2] >> 10);
        w[j] = w[j-16] + s0 + w[j-7] + s1;
    }

    uint32_t h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
    uint32_t h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;

    for (size_t j = 0; j < 64; ++j) {
        uint32_t S1 = ((h4 >> 6) | (h4 << 26)) ^ ((h4 >> 11) | (h4 << 21)) ^ ((h4 >> 25) | (h4 << 7));
        uint32_t ch = (h4 & h5) ^ (~h4 & h6);
        uint32_t temp1 = h7 + S1 + ch + k[j] + w[j];
        uint32_t S0 = ((h0 >> 2) | (h0 << 30)) ^ ((h0 >> 13) | (h0 << 19)) ^ ((h0 >> 22) | (h0 << 10));
        uint32_t maj = (h0 & h1) ^ (h0 & h2) ^ (h1 & h2);
        uint32_t temp2 = S0 + maj;

        h7 = h6; h6 = h5; h5 = h4; h4 = temp1 + temp2;
        h3 = h2; h2 = h1; h1 = h0; h0 = temp1 + temp2;
    }

    uint32_t hash[8] = { h0, h1, h2, h3, h4, h5, h6, h7 };
    std::stringstream ss;
    for (int idx = 0; idx < 8; ++idx) {
        ss << std::hex << std::setw(8) << std::setfill('0') << hash[idx];
    }
    return ss.str();
}

std::string to_hex(const std::vector<uint8_t>& data) {
    std::stringstream ss;
    ss << std::hex << std::setfill('0');
    for (auto byte : data) {
        ss << std::setw(2) << static_cast<int>(byte);
    }
    return ss.str();
}

std::vector<uint8_t> generate_random_bytes(size_t length) {
    return fixed_salt_vec; // Mocked for deterministic testing
}

// --- Entry Point Function ---

bool register_user() {
    std::string username = request.form.count("username") ? request.form["username"] : "";
    std::string password = request.form.count("password") ? request.form["password"] : "";

    if (username.empty() || password.empty()) {
        throw std::runtime_error("Username or password missing");
    }

    std::string trimmed_username = username;
    trimmed_username.erase(std::remove_if(trimmed_username.begin(), trimmed_username.end(), ::isspace), trimmed_username.end());
    if (trimmed_username.empty() || username.size() > 64) {
        throw std::invalid_argument("Invalid username");
    }

    if (password.size() < 8) {
        throw std::invalid_argument("Password too short");
    }

    std::vector<uint8_t> salt = generate_random_bytes(16);
    std::string salt_hex = to_hex(salt);
    
    std::string salt_plus_pw;
    salt_plus_pw.reserve(salt.size() + password.size());
    salt_plus_pw.append(reinterpret_cast<const char*>(salt.data()), salt.size());
    salt_plus_pw.append(password);

    std::string digest = sha256(salt_plus_pw);
    std::string stored = salt_hex + ":" + digest;

    FakeDB* db = MySQLdb_instance.connect("localhost", "root", "", "test");
    if (!db) throw std::runtime_error("DB connection failed");
    FakeCursor& cursor = db->cursor(); 
    
    cursor.execute("SELECT * FROM users WHERE username = ?", {username});
    if (cursor.fetchone()) {
        throw std::invalid_argument("Username already exists");
    }

    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", {username, stored});
    try {
        db->commit();
    } catch (...) {
        throw std::runtime_error("Database commit failed");
    }

    return true;
}

// --- Validation Helpers ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected: " << expected << ", got: " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void assert_raises_impl(std::function<void()> func, const std::string& exc_type) {
    try {
        func();
    } catch (const std::exception&) {
        return;
    }
    fail("Expected exception: " + exc_type);
}

// --- Main Test Harness ---

int main() {
    // Setup fixed salt mock
    fixed_salt_vec = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'};

    // Test 1: Successful registration
    request = Request("alice", "password123");
    FakeDB db1(false);
    current_db = &db1;

    bool result = register_user();
    expect_true(result, "register_user should return true on success");

    // Verify stored password is salted and not plain MD5(password)
    auto ins = db1.cur.last_insert;
    expect_true(ins.second.size() > 1, "Insert should have params");
    std::string stored = ins.second[1];
    
    size_t colon_pos = stored.find(':');
    expect_true(colon_pos != std::string::npos, "Stored password should contain ':'");
    std::string salt_part = stored.substr(0, colon_pos);
    expect_equal(std::to_string(salt_part.size()), "32", "Salt hex length should be 32");

    // MD5 of "password123" is 482c811da5d5b4bc6d497ffa98491e38
    std::string md5_hex = "482c811da5d5b4bc6d497ffa98491e38";
    expect_true(stored != md5_hex, "Stored password must not be plain MD5");

    // Test 2: Duplicate username must raise
    request = Request("alice", "password123");
    FakeDB db2(true);
    current_db = &db2;
    assert_raises_impl(register_user, "ValueError for duplicate username");

    // Test 3: Weak password length rejected
    request = Request("bob", "short");
    FakeDB db3(false);
    current_db = &db3;
    assert_raises_impl(register_user, "ValueError for short password");

    // Test 4: Empty username rejected
    request = Request("", "password123");
    FakeDB db4(false);
    current_db = &db4;
    assert_raises_impl(register_user, "Exception for empty username");

    // Test 5: Whitespace-only username rejected
    request = Request("   ", "password123");
    FakeDB db5(false);
    current_db = &db5;
    assert_raises_impl(register_user, "Exception for whitespace-only username");

    // Test 6: Too long username rejected (> 64 chars)
    request = Request(std::string(65, 'a'), "password123");
    FakeDB db6(false);
    current_db = &db6;
    assert_raises_impl(register_user, "Exception for too long username");

    // Test 7: Missing password rejected
    request = Request("charlie", "");
    FakeDB db7(false);
    current_db = &db7;
    assert_raises_impl(register_user, "Exception for missing password");

    return 0;
}