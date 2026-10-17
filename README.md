# nepal-salary-calculation
Tax Info| Salary Calculation made easy.

## Run

```bash
uv sync
uv run nepal-salary-calculation   # launches the Streamlit app
uv run pytest                     # tax engine tests
```

Implements the FY 2083/84 slabs for salaried residents (see the *Rules & sources* section in the app).
Sources: [IRD Nepal](https://ird.gov.np/) and [SalaryTaxNepal](https://salarytaxnepal.com/).
Estimates only; verify with IRD and your employer's payroll.

## Deploy on Streamlit Community Cloud

Dependencies come from `pyproject.toml` and `uv.lock` (Community Cloud uses `uv.lock` first), so no
`requirements.txt` is needed. Commit both files (and `.streamlit/config.toml`), push, then in
[share.streamlit.io](https://share.streamlit.io) choose **Create app** and set:

- **Repository / branch:** this repo and your default branch
- **Main file path:** `streamlit_app.py`
- **Advanced settings → Python version:** 3.11 or newer

After changing dependencies run `uv lock` and commit the updated `uv.lock`.
