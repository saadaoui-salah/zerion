# Python Best Practices

## Code Style
- Follow PEP 8 for consistent formatting
- Use meaningful variable and function names
- Keep functions small and focused
- Maximum line length of 88 characters (Black default)

## Type Hints
- Use type hints for all function signatures
- Use `Optional[T]` instead of `T | None` for Python < 3.10
- Use `Union[T1, T2]` instead of `T1 | T2` for Python < 3.10
- Use `TypeVar` for generic types

## Error Handling
- Use specific exception types
- Never catch bare `except:`
- Use `try/except/else/finally` when appropriate
- Log exceptions with context

## Performance
- Use `functools.lru_cache` for pure functions
- Use `asyncio` for I/O-bound tasks
- Use `multiprocessing` for CPU-bound tasks
- Profile before optimizing

## Testing
- Write tests for all public APIs
- Use `pytest` fixtures for setup/teardown
- Use `parametrize` for multiple test cases
- Aim for >80% code coverage

## Documentation
- Write docstrings for all public functions
- Use Google or NumPy docstring style
- Include type information in docstrings
- Document side effects and exceptions

## Security
- Never hardcode secrets
- Use environment variables for configuration
- Validate all user input
- Use parameterized queries for SQL
- Sanitize output to prevent XSS

## Common Pitfalls
- Mutable default arguments
- Late binding closures
- Generator memory consumption
- Circular imports
- GIL limitations for CPU-bound tasks
