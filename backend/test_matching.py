#!/usr/bin/env python3
"""Test matching mechanism to verify canonicalization and scoring."""

from main import canonicalize_term, normalized_set

print("=== CANONICALIZATION TESTS ===")
tests = [
    ("maths", "mathematics"),
    ("mathematics", "mathematics"),
    ("CS", "computer science"),
    ("computer science", "computer science"),
    ("AI", "artificial intelligence"),
]
for inp, expected in tests:
    result = canonicalize_term(inp)
    status = "✓" if result == expected else "✗"
    print(f"{status} '{inp}' -> '{result}' (expected '{expected}')")

print("\n=== SET MATCHING TESTS ===")
set1 = normalized_set(["maths", "gaming"])
set2 = normalized_set(["mathematics", "gaming"])
print(f"Set1: {set1}")
print(f"Set2: {set2}")
print(f"Shared: {set1 & set2}")
print(f"Count: {len(set1 & set2)}")

print("\n=== SCORE CALCULATION ===")
def calc_score(i1, i2):
    n1 = normalized_set(i1)
    n2 = normalized_set(i2)
    shared = len(n1 & n2)
    score = 20 + (shared * 15)
    return min(100, score)

print(f"Same interest: {calc_score(['maths'], ['mathematics'])}/100")
print(f"Two shared: {calc_score(['maths', 'gaming'], ['mathematics', 'gaming'])}/100")
