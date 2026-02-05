# Agent Instructions for django-imagefield

This document provides guidance for AI coding agents working on the django-imagefield codebase.

## Repository Overview

django-imagefield is a Django library for handling images with automatic processing and multiple format generation. It supports two backends: Pillow (default) and pyvips (optional, faster).

**Key directories:**
- `imagefield/` - Main package code
- `tests/testapp/` - Test application and test suite
- `docs/` - Documentation (includes README.rst)

## Development Workflow

### Before Making Changes

1. **Always read files before editing them** - Use the Read tool to understand existing code structure
2. **Check for existing tests** - Look in `tests/testapp/test_imagefield.py` for related test coverage
3. **Understand both backends** - Changes may affect both `processing_pillow.py` and `processing_vips.py`

### Testing Requirements

**Run tests through tox:**
```bash
tox -e py313-dj51  # Run specific Python/Django version
tox -l             # List available test environments
```

**Important testing practices:**
- Write tests for new functionality in `tests/testapp/test_imagefield.py`
- Place imports at the top of test files, not inside test methods
- Use `--keepdb` flag for faster test iterations (already in tox config)
- Tests must pass before changes are considered complete

### Code Style

- Follow existing code style (the project uses pre-commit hooks)
- Keep code minimal and focused - avoid over-engineering
- Prefer editing existing files over creating new ones
- Don't add comments, docstrings, or type annotations to unchanged code
- Only add error handling where truly necessary (at boundaries)

## Architecture Considerations

### Dual Backend System

The library supports two image processing backends:
- **Pillow** (`processing_pillow.py`, `backend_pillow.py`) - Default, 100% backward compatible
- **pyvips** (`processing_vips.py`, `backend_vips.py`) - Optional, faster, more memory efficient

**When adding processors:**
- Register Pillow processors with `@register_pillow`
- Register pyvips processors with `@register_vips` (if installed)
- Processors receive native backend objects (PIL.Image or pyvips.Image)
- Context-only processors can be registered for both backends

### Backward Compatibility

- `imagefield/processing.py` is a backward compatibility shim
- `register` is an alias for `register_pillow`
- Don't break existing processor names or APIs
- The `default` processor list may expand in the future
- Field deconstruction must use `django.db.models.ImageField` for migrations

## Documentation Practices

### README.rst Structure

The README serves as both GitHub documentation and Sphinx source:
- Keep documentation minimal and focused
- Use concrete examples with real code
- Link to test files for working examples using GitHub URLs
- Use the `feincms` organization in GitHub links (not `matthiask`)
- Format: reStructuredText with code-block directives
- **Heading hierarchy**: Must be consistent throughout the document:
  - `=/=` for document title (with overline)
  - `=` for level 1 headings
  - `~` for level 2 headings
  - `-` for level 3 headings
  - Don't skip levels (e.g., don't go from level 1 directly to level 3)

### When Adding Documentation

1. Add to README.rst, not separate files
2. Include practical examples
3. Write tests demonstrating the documented behavior
4. Link to those tests from the documentation
5. Keep explanations brief - assume Django knowledge
6. After editing README.rst, validate with: `uv build && uvx twine check dist/*`

## Common Patterns

### Image Processing Pipeline

Processors are middleware-style functions:
```python
@register_pillow
def my_processor(get_image, arg1, arg2):
    def processor(image, context):
        # Optional: inspect or modify context
        image = get_image(image, context)  # Call next processor
        # Modify the image
        return modified_image
    return processor
```

### Context Object

The `Context` object carries processing state:
- `ppoi` - Primary point of interest [x, y] (sealed)
- `extension` - File extension (sealed)
- `processors` - Processor list (sealed)
- `name` - Output filename (sealed)
- `save_kwargs` - Arguments passed to image.save()

Sealed attributes cannot be modified after `context.seal()` is called.

### Widget System

The widget wrapping in `fields.py` expects widget **classes**, not instances:
- `with_preview_and_ppoi()` creates a dynamic class
- It wraps any widget class with preview/PPOI functionality
- Pass classes to `formfield(widget=WidgetClass)`, not instances

## Git and Version Control

- Repository is at `github.com/feincms/django-imagefield`
- Follow conventional commit messages
- Don't commit unless explicitly requested
- Never use `--no-verify` or skip hooks
- Stage specific files by name (avoid `git add -A`)

## File Organization

**Don't create unnecessary files:**
- No new markdown/documentation files without explicit request
- Don't create helper utilities for one-time operations
- Don't add configuration for hypothetical future needs

**Settings in fields.py:**
- All settings have defaults in the `DEFAULTS` dict
- Settings are set as attributes on Django's settings object
- Use `getattr(settings, 'SETTING_NAME')` to access

## When Stuck

If you need to understand complex behavior:
1. Read the test files - they show real usage
2. Check both backend implementations for consistency
3. Look at `fields.py` for the model field behavior
4. Check `widgets.py` for form behavior

## References

- Django documentation: https://docs.djangoproject.com/
- Pillow documentation: https://pillow.readthedocs.io/
- pyvips documentation: https://libvips.github.io/pyvips/
