# Veyra Release Process & v0.2.0 Notes

## Release Checklist

1. **Clean Test Pass**: Verify all unit and property tests pass cleanly:
   ```bash
   python -m pytest python/tests
   ```
2. **CLI Smoke Test**:
   ```bash
   veyra version
   veyra doctor
   veyra config validate
   ```
3. **Examples Validation**: Verify all runnable scripts under `examples/` execute without errors.
4. **PyPI Package Build**:
   ```bash
   python -m build python/
   ```
5. **Git Tagging**:
   ```bash
   git tag -a v0.2.0 -m "Veyra v0.2.0 Release"
   ```
