# AI Video Studio

Local Windows-first workflow for turning a manually exported Google Flow ZIP or
folder into a reviewable, scene-based video project. Flow/Veo is not called by
this application.

Run the local UI and project API:

```powershell
.\.venv\Scripts\python.exe app.py serve-studio --port 8766
```

Then open `http://127.0.0.1:8766/`. Project data stays in `projects/<id>/`.
The import, source-version approval, script mapping, and video edit metadata
are real local operations. See [the local workflow guide](docs/LOCAL_STUDIO.md)
and the [dependency/license audit](docs/DEPENDENCY_LICENSES.md) before
packaging an installer.
