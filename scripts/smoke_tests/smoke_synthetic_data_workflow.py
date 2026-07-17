# smoke_synthetic_data_workflow.py -- Smoke test for faker
# (synthetic-data-workflow skill, Python identifier-generation path)
# Validates: Faker import + version, seeded reproducibility (Faker.seed),
#            the identifier-shaped providers the skill's generation patterns
#            use (name, email, phone_number, uuid4, address), and the
#            seeded-uniqueness pattern for key columns.
# The statistical-structure half of Python generation (NumPy/SciPy copulas)
# is exercised by the skill's own smoke round-trip; this test covers only
# the faker dependency added to the Dockerfile.
#
# NOT YET EXECUTED: faker==40.31.0 is added to the Dockerfile (synthetic data
# generation block) but is NOT importable until the container is rebuilt.
# Run this test after `bash rebuild_daaf.sh` from the daaf-docker folder.

# --- Config ---
import faker
from faker import Faker

SEED = 20260715

print("=== synthetic-data-workflow Smoke Test (Python: faker) ===\n")

# --- Test 1: Version check ---
print("Test 1: Version check")
ver = faker.VERSION
print(f"  faker: {ver}")
assert ver == "40.31.0", f"expected faker 40.31.0 (Dockerfile pin), got {ver}"
print("  PASS: version matches Dockerfile pin\n")

# --- Test 2: seeded reproducibility ---
print("Test 2: seeded reproducibility (audit-trail requirement)")
Faker.seed(SEED)
f1 = Faker()
run1 = [(f1.name(), f1.email(), f1.phone_number()) for _ in range(25)]
Faker.seed(SEED)
f2 = Faker()
run2 = [(f2.name(), f2.email(), f2.phone_number()) for _ in range(25)]
assert run1 == run2, "identical seeds must produce identical values"
print(f"  25 seeded rows identical across runs (first: {run1[0][0]!r})")
print("  PASS: identical seeds produce identical identifiers\n")

# --- Test 3: identifier-shaped providers used by generation-patterns-python.md ---
print("Test 3: identifier providers")
Faker.seed(SEED)
fk = Faker()
name = fk.name()
email = fk.email()
phone = fk.phone_number()
uid = fk.uuid4()
addr = fk.address()
assert isinstance(name, str) and len(name) > 0
assert "@" in email and "." in email.split("@")[1]
assert any(ch.isdigit() for ch in phone)
assert len(uid) == 36 and uid.count("-") == 4
assert isinstance(addr, str) and len(addr) > 0
print(f"  name={name!r} | email={email!r} | uuid={uid[:13]}...")
print("  PASS: all providers emit well-formed values\n")

# --- Test 4: seeded unique keys for identifier columns ---
print("Test 4: unique key generation")
Faker.seed(SEED)
fu = Faker()
ids = [fu.unique.uuid4() for _ in range(500)]
assert len(set(ids)) == 500, "unique provider must not repeat within a run"
print("  500 unique uuid4 keys generated with no collisions")
print("  PASS: unique key pattern works\n")

print("=== ALL synthetic-data-workflow Python SMOKE TESTS PASSED ===")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 17:53:32
# Command: python3 /daaf/scripts/smoke_tests/smoke_synthetic_data_workflow.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# === synthetic-data-workflow Smoke Test (Python: faker) ===
# 
# Test 1: Version check
#   faker: 40.31.0
#   PASS: version matches Dockerfile pin
# 
# Test 2: seeded reproducibility (audit-trail requirement)
#   25 seeded rows identical across runs (first: 'Benjamin Burke')
#   PASS: identical seeds produce identical identifiers
# 
# Test 3: identifier providers
#   name='Benjamin Burke' | email='jeffpope@example.org' | uuid=b6e25d57-b470...
#   PASS: all providers emit well-formed values
# 
# Test 4: unique key generation
#   500 unique uuid4 keys generated with no collisions
#   PASS: unique key pattern works
# 
# === ALL synthetic-data-workflow Python SMOKE TESTS PASSED ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
