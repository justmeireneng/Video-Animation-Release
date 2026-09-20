# AI Video Studio

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/justmeireneng/Video-Animation-Release/blob/main/colab/AI_Video_Studio.ipynb)

Agent-first workflow for turning a manually exported Google Flow ZIP plus a
narration script into a validated final MP4. The canonical command is
`python app.py build-video`; the local UI remains optional. Google Colab support
is provided by [the Run all guide](docs/COLAB.md) and the notebook in
`colab/AI_Video_Studio.ipynb`. Flow/Veo is not called by this application.

Run the local UI and project API:

```powershell
.\.venv\Scripts\python.exe app.py serve-studio --port 8766
```

Then open `http://127.0.0.1:8766/`. Project data stays in `projects/<id>/`.
The import, source-version approval, script mapping, and video edit metadata
are real local operations. See [the local workflow guide](docs/LOCAL_STUDIO.md)
and the [dependency/license audit](docs/DEPENDENCY_LICENSES.md) before
packaging an installer.
