This example is intentionally misconfigured for `azdeeploy diagnose` and `azdeeploy fix` testing.

Known issues:
- `requirements.txt` is missing on purpose.
- `.env.azure` does not define `DATABASE_URL`.
- The app reads `DATABASE_URL` and reports an error on `/db` when it is unset.

From this directory, you can use:

```bash
azdeeploy scan
azdeeploy diagnose
azdeeploy fix --dry-run
```
