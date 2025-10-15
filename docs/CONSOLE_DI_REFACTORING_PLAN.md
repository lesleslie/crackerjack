# Console Dependency Injection Refactoring Plan

This document outlines the plan to refactor the `crackerjack` codebase to use a consistent dependency injection (DI) pattern for the `Console` object, eliminating direct imports and parameter passing.

## Current State Analysis

The current usage of the `console` object is mixed and falls into four main categories:
1.  **Direct Import**: A few files use `from acb.console import console`.
2.  **Class-based `self.console`**: The majority of components receive the `console` object in their `__init__` method and store it as a class instance.
3.  **Global `console` in Scripts/CLI**: Application entry points use a globally available `console` object.
4.  **Mocking in Tests**: Tests use patching to mock the console, which can be simplified with DI.

## Refactoring Plan

The refactoring will be executed in the following phases:

### ☑ Step 1: Centralize Console Registration
- [x] **Task**: Find the primary application entry point (e.g., `crackerjack/__main__.py`).
- [x] **Task**: Ensure the `acb.console.console` instance is registered with `acb.depends.set()` once at application startup. This will make the `Console` available for injection throughout the application.

### ☑ Step 2: Refactor Class-based Usage (`self.console`)
- [x] **Task**: Identify all classes that receive `console` as an `__init__` parameter.
- [x] **Task**: For each class, remove the `console` parameter from `__init__`.
- [x] **Task**: Apply the `@depends.inject` decorator to the `__init__` method and add `console: Inject[Console]` to its signature.
- [x] **Task**: Update all instantiation calls of these classes to remove the `console` argument.

### ☑ Step 3: Refactor Direct Imports
- [x] **Task**: Identify all files using `from acb.console import console`.
- [x] **Task**: For each function in these files using the `console`, apply the `@depends.inject` decorator and add the `console: Inject[Console]` parameter.

### ☑ Step 4: Refactor CLI/Script Usage
- [x] **Task**: For entry-point scripts using a global `console`, refactor the logic into dedicated functions.
- [x] **Task**: Apply the `@depends.inject` decorator to these new functions to provide them with the `Console`.

### ☐ Step 5: Review and Finalize
- [ ] **Task**: Review all changes to ensure consistency.
- [ ] **Task**: Update tests to use DI for mocking the console where appropriate.
- [ ] **Task**: Mark this plan as complete.
