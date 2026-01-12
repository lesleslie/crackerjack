# Sprint 7: Coverage Phase 6 - Plan

**Date**: 2026-01-11
**Goal**: Create comprehensive tests for 2-3 high-impact files with 0% coverage
**Status**: 🔄 IN PROGRESS

---

## Target Files Selected

Based on coverage analysis (17 files with 0% coverage and 50+ statements):

### 1. **services/coverage_ratchet.py** (190 statements) ⭐ HIGH PRIORITY
- **Why**: Core coverage ratchet system - critical quality gate
- **Expected complexity**: Medium (business logic with configuration)
- **Target coverage**: 65-70%

### 2. **services/anomaly_detector.py** (163 statements) ⭐ HIGH PRIORITY
- **Why**: Domain-specific anomaly detection - interesting logic to test
- **Expected complexity**: Medium-High (statistical algorithms, conditional dependencies)
- **Target coverage**: 60-65%

### 3. **services/regex_utils.py** (179 statements) ⭐ MEDIUM PRIORITY
- **Why**: Regex utilities - foundational pattern matching
- **Expected complexity**: Low-Medium (pure functions, minimal dependencies)
- **Target coverage**: 70-75%

**Total Impact**: 532 statements, targeting ~65% average coverage improvement

---

## Sprint Strategy

### Key Principles (Learned from Sprints 2-6)

1. ✅ **READ IMPLEMENTATION FIRST** - Critical for avoiding test failures
   - Read entire file before writing any tests
   - Document all classes, methods, and key logic
   - Note any conditional branches or edge cases

2. ✅ **Use Module-Level Import Pattern** - Avoids pytest conflicts
   ```python
   from crackerjack.services import coverage_ratchet
   CoverageRatchet = coverage_ratchet.CoverageRatchet
   ```

3. ✅ **Test Public API Methods** - Focus on user-facing behavior
   - Constructor initialization
   - Public methods with different scenarios
   - Error cases and edge conditions

4. ✅ **Target 60-70% Coverage** - Balance thoroughness with pragmatism
   - Focus on core logic paths
   - Accept missing visual/formatting code
   - Document intentionally untested code

5. ✅ **Maintain 100% Test Pass Rate** - Quality over quantity
   - Read implementation to fix failures
   - Never guess field names or signatures
   - Document any implementation bugs found

---

## Success Criteria

- ✅ All tests passing (100% pass rate)
- ✅ 60-70% coverage per file average
- ✅ Zero implementation bugs introduced
- ✅ Comprehensive documentation created
- ✅ Module-level import pattern used

---

## Timeline Estimate

Based on previous sprints:
- Sprint 2b: 109 tests, ~4 hours (with 24 failures to fix)
- Sprint 3: 124 tests, ~3 hours (with 12 failures to fix)
- Sprint 4: 112 tests, ~3 hours (with 12 failures to fix)
- Sprint 5: 50 tests, ~2.5 hours (with 8 failures fixed)
- Sprint 6: 56 tests, ~1 hour (with 1 failure fixed)

**Sprint 7 Estimate**: 2-3 hours for ~60-80 tests

**Optimistic Scenario**: ~60 tests in 2 hours (applying lessons learned)
**Conservative Scenario**: ~80 tests in 3 hours (allowing for complexity)

---

## Risk Assessment

**Low Risk** ✅:
- Pattern established across 6 sprints (452 tests, 100% pass rate)
- Module-level import pattern prevents pytest conflicts
- Reading implementation first prevents test failures

**Medium Risk** ⚠️:
- coverage_ratchet.py may have complex business logic
- anomaly_detector.py may have conditional dependencies (like scipy)
- regex_utils.py may have complex pattern matching

**Mitigation**:
- Read implementation files thoroughly before writing tests
- Start with simpler tests (initialization, basic methods)
- Use mocking appropriately for external dependencies

---

## Next Steps

1. ✅ Read `coverage_ratchet.py` implementation
2. ✅ Document all classes, methods, and logic
3. ✅ Create comprehensive tests for coverage_ratchet.py
4. ✅ Run tests and fix any failures
5. ✅ Repeat for anomaly_detector.py
6. ✅ Repeat for regex_utils.py (if time permits)
7. ✅ Create Sprint 7 completion documentation

---

**Sprint 7 Status**: 🟡 PLANNING - Ready to start implementation
**Overall Progress**: Sprint 6 complete (452 tests across 12 files)
