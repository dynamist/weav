{
  mkShell,
  uv,
  pythonSet,
  editableVenv,
}:
mkShell {
  packages = [
    editableVenv
    uv
  ];
  env = {
    UV_NO_SYNC = "1";
    UV_PYTHON = pythonSet.python.interpreter;
    UV_PYTHON_DOWNLOADS = "never";
  };
  shellHook = # bash
    ''
      unset PYTHONPATH
      export REPO_ROOT=$(git rev-parse --show-toplevel)
    '';
}
