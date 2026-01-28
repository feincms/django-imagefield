# Running Tests

## Basic Tests

To run the basic test suite (Pillow backend only):

```bash
tox -e py310-dj42
```

## Full Test Suite (including vips backend)

To run the complete test suite including vips backend tests, you must install pyvips:

```bash
pip install pyvips[binary]>=2.2
tox -e py310-dj42
```

## Test Coverage

The test suite includes:

- **44 tests** for Pillow backend and core functionality
- **31 additional tests** for vips backend functionality
  - 12 VipsBackendTestCase tests (backend methods and processors)
  - 19 VipsIntegrationTest tests (full ImageField integration)

**Total: 85 tests** when pyvips is installed.

### Verification Tests

The vips backend tests include several verification tests to ensure they're actually using the vips backend:

1. **`test_backend_is_vips`** - Verifies `get_backend().name == "vips"`
2. **`test_processing_uses_vips_images`** - Verifies `backend.open()` returns `pyvips.Image`, not `PIL.Image`
3. **`test_backend_uses_vips_processors`** - Verifies backend uses `VIPS_PROCESSORS`, not `PILLOW_PROCESSORS`
4. **`test_processor_receives_vips_image`** - Creates a custom processor and verifies it receives `pyvips.Image` objects
5. **`test_pillow_backend_never_used`** - Uses mocking to ensure `PillowBackend` is never instantiated

These tests ensure there's no possibility of accidentally testing with the Pillow backend when vips is configured.

## Note on Test Philosophy

The vips backend tests **do not skip** when pyvips is not installed - they fail loudly. This ensures that:

1. In CI/development environments where pyvips should be present, missing dependencies are caught immediately
2. Tests actually test functionality rather than silently skipping
3. Test coverage accurately reflects what's actually being tested

If you see `ModuleNotFoundError: No module named 'pyvips'`, install pyvips to run the full test suite.
